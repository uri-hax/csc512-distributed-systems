/*
 * Buffer pool manager — maintains a fixed pool of pages in memory,
 * evicts LRU pages when full, and tracks read/write statistics.
 *
 * Submitted by: student
 * Assignment: Lab 5 - Memory Management
 *
 * The pool is intentionally sized to stress available memory:
 *   - Each page is 64KB (larger than typical to show memory pressure faster)
 *   - Pool holds up to 512 pages = 32MB total
 *   - Workload accesses 10000 unique pages, forcing constant eviction
 *
 * Under memory_ceiling (64MB): pool allocation starts failing partway through
 * setup, triggering the cerr error paths and a clean shutdown.
 * Under memory_squeeze: pool runs fine then hits allocation failures as
 * the limit drops below resident memory.
 * Under cpu profiles: batch times increase proportionally.
 */

#include <iostream>
#include <unordered_map>
#include <list>
#include <vector>
#include <string>
#include <chrono>
#include <cstring>
#include <cerrno>
#include <cstdlib>

static const int PAGE_SIZE    = 64 * 1024;   // 64 KB per page
static const int POOL_PAGES   = 512;          // 32 MB total pool
static const int TOTAL_PAGES  = 10000;        // working set larger than pool
static const int OPS_PER_BATCH = 200;

// ── Page ─────────────────────────────────────────────────────────────────────

struct Page {
    int   page_id;
    bool  dirty;
    char *data;

    Page(int id) : page_id(id), dirty(false), data(nullptr) {
        data = new (std::nothrow) char[PAGE_SIZE];
        if (!data) {
            std::cerr << "ERROR: failed to allocate page " << id
                      << " (" << PAGE_SIZE / 1024 << " KB): "
                      << std::strerror(errno) << std::endl;
        }
    }

    ~Page() {
        delete[] data;
        data = nullptr;
    }

    bool valid() const { return data != nullptr; }

    void write(int offset, char val) {
        if (!valid()) {
            std::cerr << "ERROR: write to invalid page " << page_id << std::endl;
            return;
        }
        if (offset >= PAGE_SIZE) {
            std::cerr << "ERROR: write out of bounds on page " << page_id
                      << " (offset=" << offset << ")" << std::endl;
            return;
        }
        data[offset] = val;
        dirty = true;
    }
};

// ── Buffer pool ───────────────────────────────────────────────────────────────

class BufferPool {
public:
    int  capacity;
    int  hits;
    int  misses;
    int  evictions;
    int  alloc_failures;
    bool healthy;

    explicit BufferPool(int cap) : capacity(cap), hits(0), misses(0),
                                    evictions(0), alloc_failures(0),
                                    healthy(true) {
        if (cap <= 0) {
            std::cerr << "ERROR: buffer pool capacity must be > 0 (got "
                      << cap << ")" << std::endl;
            healthy = false;
        }
    }

    ~BufferPool() {
        int freed = 0;
        for (auto& pair : pool) {
            delete pair.second;
            freed++;
        }
        pool.clear();
        lru_order.clear();
        if (freed > 0) {
            std::cerr << "ERR: pool shutdown: freed " << freed
                    << " pages (" << (freed * PAGE_SIZE / 1024) << " KB)"
                    << std::endl;
            std::cerr.flush();
        }
    }

    Page* fetch(int page_id) {
        if (!healthy) {
            std::cerr << "ERROR: fetch on unhealthy pool (page "
                      << page_id << ")" << std::endl;
            return nullptr;
        }

        auto it = pool.find(page_id);
        if (it != pool.end()) {
            hits++;
            lru_order.remove(page_id);
            lru_order.push_front(page_id);
            return it->second;
        }

        misses++;

        if ((int)pool.size() >= capacity) {
            if (!evict()) {
                std::cerr << "ERROR: pool full and eviction failed — "
                          << "cannot fetch page " << page_id << std::endl;
                healthy = false;
                return nullptr;
            }
        }

        Page* page = new (std::nothrow) Page(page_id);
        if (!page) {
            std::cerr << "ERROR: failed to allocate Page struct for page "
                      << page_id << ": " << std::strerror(errno) << std::endl;
            alloc_failures++;
            if (alloc_failures >= 3) {
                std::cerr << "ERROR: " << alloc_failures
                          << " consecutive allocation failures — "
                          << "marking pool unhealthy and shutting down"
                          << std::endl;
                healthy = false;
            }
            return nullptr;
        }

        if (!page->valid()) {
            std::cerr << "ERROR: page " << page_id
                      << " data buffer is null out of memory ("
                      << (pool.size() * PAGE_SIZE / 1024) << " KB in use)"
                      << std::endl;
            alloc_failures++;
            delete page;
            if (alloc_failures >= 3) {
                std::cerr << "ERROR: " << alloc_failures
                          << " consecutive allocation failures — "
                          << "marking pool unhealthy and shutting down"
                          << std::endl;
                healthy = false;
            }
            return nullptr;
        }

        // Reset failure count on success
        alloc_failures = 0;

        // Simulate loading page from disk
        std::memset(page->data, (page_id & 0xFF), PAGE_SIZE);

        pool[page_id] = page;
        lru_order.push_front(page_id);
        return page;
    }

    void print_stats(double elapsed) const {
        int total    = hits + misses;
        double hr    = total > 0 ? 100.0 * hits / total : 0.0;
        double mb_in_use = pool.size() * PAGE_SIZE / (1024.0 * 1024.0);
        std::cout << "[" << elapsed << "s]"
                  << "  pool=" << pool.size() << "/" << capacity
                  << "  (" << mb_in_use << " MB)"
                  << "  hit_rate=" << hr << "%"
                  << "  evictions=" << evictions
                  << "  healthy=" << (healthy ? "yes" : "NO")
                  << std::endl;
    }

private:
    std::unordered_map<int, Page*> pool;
    std::list<int>                 lru_order;

    bool evict() {
        if (lru_order.empty()) return false;

        int   victim_id = lru_order.back();
        lru_order.pop_back();
        auto  it        = pool.find(victim_id);
        if (it == pool.end()) return false;

        if (it->second->dirty) {
            // Simulate write-back: touch the data so it's CPU-visible
            volatile char sum = 0;
            for (int i = 0; i < PAGE_SIZE; i += 256)
                sum ^= it->second->data[i];
            (void)sum;
        }

        delete it->second;
        pool.erase(it);
        evictions++;
        return true;
    }
};

// ── Workload ──────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
    int pool_size = POOL_PAGES;
    if (argc > 1) {
        pool_size = std::atoi(argv[1]);
        if (pool_size <= 0) {
            std::cerr << "ERROR: invalid pool size '" << argv[1]
                      << "' must be a positive integer" << std::endl;
            return 1;
        }
    }

    double pool_mb = pool_size * PAGE_SIZE / (1024.0 * 1024.0);
    std::cout << "Buffer pool manager starting" << std::endl;
    std::cout << "Pool capacity : " << pool_size << " pages ("
              << pool_mb << " MB)" << std::endl;
    std::cout << "Page size     : " << PAGE_SIZE / 1024 << " KB" << std::endl;
    std::cout << "Working set   : " << TOTAL_PAGES << " pages ("
              << (TOTAL_PAGES * PAGE_SIZE / 1024 / 1024) << " MB)" << std::endl;
    std::cout << std::endl;

    BufferPool pool(pool_size);
    if (!pool.healthy) {
        std::cerr << "ERROR: failed to initialize buffer pool" << std::endl;
        return 1;
    }

    auto   start    = std::chrono::steady_clock::now();
    int    total_ops = 0;
    int    batch     = 0;

    // 80% hot set (first 200 pages), 20% cold (remaining 9800)
    // This ensures constant eviction pressure
    srand(42);

    while (pool.healthy) {
        auto now     = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - start).count();
        if (elapsed >= 60.0) break;

        for (int op = 0; op < OPS_PER_BATCH && pool.healthy; op++) {
            int page_id;
            if (rand() % 100 < 80)
                page_id = rand() % 200;
            else
                page_id = 200 + rand() % (TOTAL_PAGES - 200);

            Page* page = pool.fetch(page_id);
            if (!page) {
                if (!pool.healthy) {
                    std::cerr << "ERROR: pool is unhealthy after fetch failure - "
                              << "shutting down after "
                              << total_ops << " operations" << std::endl;
                }
                break;
            }

            // 30% writes
            if (rand() % 100 < 30)
                page->write(rand() % PAGE_SIZE, (char)(total_ops & 0xFF));

            total_ops++;
        }

        batch++;
        auto now2    = std::chrono::steady_clock::now();
        double elapsed2 = std::chrono::duration<double>(now2 - start).count();
        pool.print_stats(elapsed2);
    }

    // Report outcome
    if (!pool.healthy) {
        std::cerr << "ERROR: pool became unhealthy exiting with error" << std::endl;
        std::cout << "Completed " << total_ops
                  << " operations before failure" << std::endl;
        return 1;
    }

    std::cout << "\nNormal shutdown." << std::endl;
    std::cout << "Total operations: " << total_ops << std::endl;
    return 0;
}