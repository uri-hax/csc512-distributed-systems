#include "kernel.hh"
#include "k-apic.hh"
#include "k-vmiter.hh"
#include <atomic>

// kernel.cc
//
//    This is the kernel.


// INITIAL PHYSICAL MEMORY LAYOUT
//
//  +-------------- Base Memory --------------+
//  v                                         v
// +-----+--------------------+----------------+--------------------+---------/
// |     | Kernel      Kernel |       :    I/O | App 1        App 1 | App 2
// |     | Code + Data  Stack |  ...  : Memory | Code + Data  Stack | Code ...
// +-----+--------------------+----------------+--------------------+---------/
// 0  0x40000              0x80000 0xA0000 0x100000             0x140000
//                                             ^
//                                             | \___ PROC_SIZE ___/
//                                      PROC_START_ADDR

#define PROC_SIZE 0x40000       // initial state only

proc ptable[NPROC];             // array of process descriptors
                                // Note that `ptable[0]` is never used.
proc* current;                  // pointer to currently executing proc

#define HZ 100                  // timer interrupt frequency (interrupts/sec)
static std::atomic<unsigned long> ticks; // # timer interrupts so far


// Memory state
//    Information about physical page with address `pa` is stored in
//    `pages[pa / PAGESIZE]`. In the handout code, each `pages` entry
//    holds an `refcount` member, which is 0 for free pages.
//    You can change this as you see fit.

pageinfo pages[NPAGES];


[[noreturn]] void schedule();
[[noreturn]] void run(proc* p);
void exception(regstate* regs);
uintptr_t syscall(regstate* regs);
void memshow();
static void process_setup(pid_t pid, const char* program_name);


// kernel(command)
//    Initialize the hardware and processes and start running. The `command`
//    string is an optional string passed from the boot loader.

void kernel(const char* command) {
    // Initialize hardware.
    init_hardware();
    log_printf("Starting WeensyOS\n");

    // Initialize timer interrupt.
    ticks = 1;
    init_timer(HZ);

    // Clear screen.
    console_clear();

    // (re-)Initialize the kernel page table.
    for (vmiter it(kernel_pagetable); it.va() < MEMSIZE_PHYSICAL; it += PAGESIZE) {
        if (it.va() == CONSOLE_ADDR) {
            // Map console memory with user-mode permissions.
            it.map(it.va(), PTE_P | PTE_W | PTE_U);
        } else if (it.va() == 0) {
            // nullptr is inaccessible even to the kernel
            it.map(it.va(), 0);
        } else if (it.va() < PROC_START_ADDR) {
            // Map kernel memory with kernel-mode permissions.
            it.map(it.va(), PTE_P | PTE_W);
        } else {
            // Map process memory with user-mode permissions.
            it.map(it.va(), PTE_P | PTE_W | PTE_U);
        }
    }

    // Set up process descriptors.
    for (pid_t i = 0; i < NPROC; i++) {
        ptable[i].pid = i;
        ptable[i].state = P_FREE;
    }
    if (command && program_loader(command).present()) {
        process_setup(1, command);
    } else {
        process_setup(1, "allocator");
        process_setup(2, "allocator2");
        process_setup(3, "allocator3");
        process_setup(4, "allocator4");
    }

    // Switch to the first process using run().
    run(&ptable[1]);
}


// kalloc(sz)
//    Kernel memory allocator. Allocates `sz` contiguous bytes and
//    returns a pointer to the allocated memory (the physical address of
//    the newly allocated memory), or `nullptr` on failure.
//
//    The returned memory is initialized to 0xCC, which corresponds to
//    the x86 instruction `int3` (this may help you debug). You can
//    reset it to something more useful.
//
//    On WeensyOS, `kalloc` is a page-based allocator: if `sz > PAGESIZE`
//    the allocation fails; if `sz < PAGESIZE` it allocates a whole page
//    anyway.
//
//    The stencil code returns the next allocatable free page it can find,
//    but it never reuses pages or supports freeing memory 

static uintptr_t next_alloc_pa;

void* kalloc(size_t sz) {
    if (sz > PAGESIZE) {
        return nullptr;
    }

    check_pagetable(kernel_pagetable);

    while (next_alloc_pa < MEMSIZE_PHYSICAL) {
        uintptr_t pa = next_alloc_pa;
        next_alloc_pa += PAGESIZE;

        /**
         * There's some very weird stuff going on around kernel code
         * I believe this is in part due to the kernel code not starting at KERNEL_START_ADDR
         * Not exactly sure why it doesn't start at the start address, could just be a rendering issue
         * My best guess is something to do with the kernel_gdt_segments, which keeps track
         * of the addresses of the different addresses of the kernel
         * Whatever the root cause, memset seems to get "stuck" (for some reason just doesn't return)
         * I've also seen things like page faults (exception 14) and invalid opcode (exception 6)
         * So we're just not going to allocate anything around that area
         * If you can figure out the reason this is happening/fix it, you'll be my favorite
         * Comment the following if statement during step 3, if you dare...
         */
        if (next_alloc_pa == KERNEL_START_ADDR) {
            next_alloc_pa = (uintptr_t) 0x080000;
        }

        if (allocatable_physical_address(pa) && !pages[pa / PAGESIZE].used()) {
            pages[pa / PAGESIZE].refcount = 1;
            memset((void*) pa, 0xCC, PAGESIZE);
            return (void*) pa;
        }
    }
    return nullptr;
}


// kfree(kptr)
//    Frees `kptr`, which must have been previously returned by `kalloc`.
//    If `kptr == nullptr` does nothing.
//    *YOU DO NO NEED TO IMPLEMENT THIS* - though if you would like an extra challenge feel free

void kfree(void* kptr) {
    (void) kptr;
    assert(false);
}


// process_setup(pid, program_name)
//    Loads application program `program_name` as process number `pid`.
//    This loads the application's code and data into memory, sets its
//    %rip and %rsp, gives it a stack page, and marks it as runnable.

void process_setup(pid_t pid, const char* program_name) {
    init_process(&ptable[pid], 0);

    // Create a new page table for the process
    ptable[pid].pagetable = (x86_64_pagetable*) kalloc(PAGESIZE);
    memset(ptable[pid].pagetable, 0, PAGESIZE);

    // Map kernel memory into this pagetable
    for (vmiter k_it(kernel_pagetable, 0), p_it(ptable[pid].pagetable, 0);
        k_it.va() < PROC_START_ADDR;
        k_it += PAGESIZE, p_it += PAGESIZE) {
        if (k_it.va() == CONSOLE_ADDR) {
            p_it.map(k_it.pa(), PTE_P | PTE_W | PTE_U);
        } else if (k_it.present()) {
            p_it.map(k_it.pa(), k_it.perm());
        }
    }

    program_loader loader(program_name);

    // Allocate and map memory for each segment
    for (loader.reset(); loader.present(); ++loader) {
        for (uintptr_t va = round_down(loader.va(), PAGESIZE);
             va < loader.va() + loader.size();
             va += PAGESIZE) {
            void* pa = kalloc(PAGESIZE);
            assert(pa != nullptr);
            vmiter(ptable[pid].pagetable, va).map((uintptr_t) pa, PTE_P | PTE_W | PTE_U);
            memset(pa, 0, PAGESIZE);
        }

        vmiter it(ptable[pid].pagetable, loader.va());
        assert(it.present());
        memcpy((void*) it.pa(), loader.data(), loader.data_size());
    }

    ptable[pid].regs.reg_rip = loader.entry();

    // Allocate and map stack at 0x300000 (MEMSIZE_VIRTUAL)
    uintptr_t stack_addr = MEMSIZE_VIRTUAL - PAGESIZE;
    void* stack_pa = kalloc(PAGESIZE);
    assert(stack_pa != nullptr);
    vmiter(ptable[pid].pagetable, stack_addr).map((uintptr_t) stack_pa, PTE_P | PTE_W | PTE_U);
    ptable[pid].regs.reg_rsp = stack_addr + PAGESIZE;  // Stack grows down from here

    // Process ready to run
    ptable[pid].state = P_RUNNABLE;
}


// exception(regs)
//    Exception handler (for interrupts, traps, and faults).
//    You should *not* have to edit this function.
//
//    The register values from exception time are stored in `regs`.
//    The processor responds to an exception by saving application state on
//    the kernel's stack, then jumping to kernel assembly code (see
//    k-exception.S). That code saves more registers on the kernel's stack,
//    then calls exception(). This way, the process can be resumed right where
//    it left off before the exception. The pushed registers are popped and
//    restored before returning to the process (see k-exception.S).
//
//    Note that hardware interrupts are disabled when the kernel is running.

void exception(regstate* regs) {
    //     // Check if it's a page fault (exception 14)
    // if (regs->reg_intno == INT_PAGEFAULT) {
    //     // Get faulting address from CR2
    //     uintptr_t fault_addr = rcr2();
        
    //     // Check if the address is in user space
    //     if (fault_addr >= PROC_START_ADDR && fault_addr < MEMSIZE_VIRTUAL) {
    //         // Try to handle it by allocating a page
    //         if (syscall_page_alloc(fault_addr) == 0) {
    //             return;  // Successfully handled
    //         }
    //     }
        
    //     // If we get here, it's a real fault
    //     current->state = P_BROKEN;
    //     snprintf(current->name, sizeof(current->name), "<Fault %d>", regs->reg_intno);
    // }
    // Copy the saved registers into the `current` process descriptor.
    current->regs = *regs;
    regs = &current->regs;

    // It can be useful to log events using `log_printf`.
    // Events logged this way are stored in the host's `log.txt` file.
    /* log_printf("proc %d: exception %d at rip %p\n",
                current->pid, regs->reg_intno, regs->reg_rip); */

    // Show the current cursor location and memory state (unless this is a kernel fault).
    console_show_cursor(cursorpos);
    if (regs->reg_intno != INT_PF || (regs->reg_errcode & PFERR_USER)) {
        memshow();
    }

    // If Control-C was typed, exit the virtual machine.
    check_keyboard();


    // Actually handle the exception.
    switch (regs->reg_intno) {

    case INT_IRQ + IRQ_TIMER:
        ++ticks;
        lapicstate::get().ack();
        schedule();
        break;                  /* will not be reached */

    case INT_PF: {
        // Analyze faulting address and access type.
        uintptr_t addr = rdcr2();
        const char* operation = regs->reg_errcode & PFERR_WRITE
                ? "write" : "read";
        const char* problem = regs->reg_errcode & PFERR_PRESENT
                ? "protection problem" : "missing page";

        console_printf(CPOS(24, 0), 0x0C00,
                       "Process %d page fault for %p (%s %s, rip=%p)!\n",
                       current->pid, addr, operation, problem, regs->reg_rip);

        if (!(regs->reg_errcode & PFERR_USER)) {
            panic("Kernel page fault for %p (%s %s, rip=%p)!\n",
                  addr, operation, problem, regs->reg_rip);
        }
        
        current->state = P_BROKEN;
        break;
    }

    default:
        panic("Unexpected exception %d!\n", regs->reg_intno);

    }

    // Return to the current process (or run something else).
    if (current->state == P_RUNNABLE) {
        run(current);
    } else {
        schedule();
    }
}

// Headers for helper functions used by syscall.
int syscall_page_alloc(uintptr_t addr);
pid_t syscall_fork();
void syscall_exit();

// syscall(regs)
//    System call handler.
//
//    The register values from system call time are stored in `regs`.
//    The return value, if any, is returned to the user process in `%rax`.
//
//    Note that hardware interrupts are disabled when the kernel is running.
// *YOU SHOULD NO NEED TO EDIT THIS*

uintptr_t syscall(regstate* regs) {
    // Copy the saved registers into the `current` process descriptor.
    current->regs = *regs;
    regs = &current->regs;

    // It can be useful to log events using `log_printf`.
    // Events logged this way are stored in the host's `log.txt` file.
    /* log_printf("proc %d: syscall %d at rip %p\n",
                  current->pid, regs->reg_rax, regs->reg_rip); */

    // Show the current cursor location and memory state (unless this is a kernel fault).
    console_show_cursor(cursorpos);
    memshow();

    // If Control-C was typed, exit the virtual machine.
    check_keyboard();

    // Actually handle the exception.
    switch (regs->reg_rax) {

    case SYSCALL_PANIC:
        panic(nullptr); // does not return

    case SYSCALL_GETPID:
        return current->pid;

    case SYSCALL_YIELD:
        current->regs.reg_rax = 0;
        schedule(); // does not return

    case SYSCALL_PAGE_ALLOC:
        return syscall_page_alloc(current->regs.reg_rdi);

    case SYSCALL_FORK:
        return syscall_fork();

    case SYSCALL_EXIT:
        syscall_exit();
        schedule(); // does not return

    default:
        panic("Unexpected system call %ld!\n", regs->reg_rax);

    }

    panic("Should not get here!\n");
}


// syscall_page_alloc(addr)
//    Helper function that handles the SYSCALL_PAGE_ALLOC system call.
//    This function implement the specification for `sys_page_alloc`
//    in `u-lib.hh` (but in the stencil code, it does not - you will
//    have to change this).

int syscall_page_alloc(uintptr_t addr) {
    // Check that the address is page-aligned and in user space
    if (addr % PAGESIZE != 0 || addr < PROC_START_ADDR || addr >= MEMSIZE_VIRTUAL) {
        return -1;
    }

    // Check if physical page is available
    void* pa = kalloc(PAGESIZE);
    if (!pa) {
        return -1;
    }

    // Map the virtual address to the physical address
    vmiter it(current->pagetable, addr);
    if (it.try_map((uintptr_t) pa, PTE_P | PTE_W | PTE_U) < 0) {
        kfree(pa);  // Free the page if mapping fails
        return -1;
    }
    memset(pa, 0, PAGESIZE);
    return 0;
}


// syscall_fork()
//    Handles the SYSCALL_FORK system call. This function
//    implements the specification for `sys_fork` in `u-lib.hh`.
// *YOU DO NOT NEED TO IMPLEMENT THIS* - though if you want an extra challenge feel free

pid_t syscall_fork() {
    panic("Unexpected system call %ld!\n", SYSCALL_FORK);
}


// syscall_exit()
//    Handles the SYSCALL_EXIT system call. This function
//    implements the specification for `sys_exit` in `u-lib.hh`.
// *YOU DO NOT NEED TO IMPLEMENT THIS* - though if you want an extra challenge feel free

void syscall_exit() {
    panic("Unexpected system call %ld!\n", SYSCALL_EXIT);
}


// schedule
//    Picks the next process to run and then run it.
//    If there are no runnable processes, spins forever.
//    You should *not* have to edit this function.
// *DO NOT EDIT THIS*

void schedule() {
    pid_t pid = current->pid;
    for (unsigned spins = 1; true; ++spins) {
        pid = (pid + 1) % NPROC; 
        if (ptable[pid].state == P_RUNNABLE) {
            run(&ptable[pid]);
        }

        // If Control-C was typed, exit the virtual machine.
        check_keyboard();

        // If spinning forever, show the memviewer.
        if (spins % (1 << 12) == 0) {
            memshow();
            log_printf("%u\n", spins);
        }
    }
}


// run(p)
//    Runs process `p`. This involves setting `current = p` and calling
//    `exception_return` to restore its page table and registers.
//    You should *not* have to edit this function.
// *DO NOT EDIT THIS*

void run(proc* p) {
    assert(p->state == P_RUNNABLE);
    current = p;

    // Check the process's current pagetable.
    check_pagetable(p->pagetable);

    // This function is defined in k-exception.S. It restores the process's
    // registers then jumps back to user mode.
    exception_return(p);

    // should never get here
    while (true) {
    }
}


// memshow()
//    Draws a picture of memory (physical and virtual) on the CGA console.
//    Switches to a new process's virtual memory map every 0.25 sec.
//    Uses `console_memviewer()`, a function defined in `k-memviewer.cc`.
//    You should *not* have to edit this function.
// *DO NOT EDIT THIS*

void memshow() {
    static unsigned last_ticks = 0;
    static int showing = 0;
    bool switched_process = false;

    // switch to a new process every 0.25 sec
    if (last_ticks == 0 || ticks - last_ticks >= HZ / 2) {
        last_ticks = ticks;
        showing = (showing + 1) % NPROC;
        switched_process = true;
    }

    proc* p = nullptr;
    for (int search = 0; !p && search < NPROC; ++search) {
        if (ptable[showing].state != P_FREE
            && ptable[showing].pagetable) {
            p = &ptable[showing];
        } else {
            showing = (showing + 1) % NPROC;
        }
    }

    extern void console_memviewer(proc* vmp, bool switched_process);
    console_memviewer(p, switched_process);
}
