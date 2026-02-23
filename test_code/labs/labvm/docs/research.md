### Find a recent research paper relating to advancements in Virtual Memory

##### Paper Name, Authors, and Year Published
MAGE: Nearly Zero-Cost Virtual Memory for Secure Computation
Authors: 
Sam Kumar, David E. Culler, and Raluca Ada Popa, University of California, Berkeley
This paper is included in the Proceedings of the 15th USENIX Symposium on Operating Systems  Design and Implementation. July 14–16, 2021

##### Desribe the papers Contribution (2-4 sentences)
The authors of this paper created MAGE, a userspace execution engine designed to handle memory management for secure computation (SC). They leverage that fact that all SC workloads are oblivious, meaning the memory access patterns do not depend on the input data (avoiding conditionals etc). Rather than reacting to page faults, the MAGE engine plans memory access in advanced to optimize paging and prefetching. The results of this are that MAGE outperforms standard OS virtual memory systems when the SC computations exceed physical memory. 

#### Create a Real-World Analogy Explaining the Contribution (2-4 sentences)
Most home-cooks, when preparing from a recipe, will pull out each ingrediant one at a time as they are used in the recipe. A traditional operating system behaves in much the same way. The home-cook may wait until an ingredient is needed to go to the pantry and a traditional OS will wait until a page fault occurs to access virtual memory. 
On the other hand, a professional chef in a restaurant kitchen will prepare and plan each ingredient before service (mice-en-place) so that there are no delays to their cooking time. The MAGE Engine performs in the same manner, preaccessing virtual memory to optimize performance.

#### Citation:
https://www.usenix.org/conference/osdi21/presentation/kumar

### Find a recent research paper relating to advancements in Memory Safety

##### Paper Name, Authors, and Year Published
HeapCheck: Low-cost Hardware Support for Memory Safety
Authors: Gururaj Saileshwar, Rick Boivie, Tong Chen, Benjamin Segal, Alper Buyuktosunoglu
Published: 23 January 2022

##### Desribe the papers Contribution (2-4 sentences)
HeapCheck is a hardware-based solution to some common memory safety issues in C and C++ programs. It works by using the unused bits in a 64-bit pointer to store values in a table, this allows for more robust bounds-checking to ensure there is no unsafe memory access. A critical point of the HeapCheck design is that there are no changes made to the source code to ensure backwards compatibility. It can also identify problems across shared libraries which is something similar tools have been unable to do. There is an introduced performance penalty of 1.5% slowdown, which the authors describe as sufficiently acceptable.

#### Create a Real-World Analogy Explaining the Contribution (2-4 sentences)
Memory handling in C/C++ is a lot like a classroom full of preschoolers. They may try to grab too many crayons, or one kid may try to sit on three chairs at once while others try to move one seat over, this can cause a lot of confusion and result in unequal supplies. HeapCheck is like a good teacher, they may write out name cards for each chair or ensure all kids get exactly one crayon. They can do this so efficiently that the students may not even notice they are being managed and this avoids confusion, mix-ups, or errors. 


#### Citation:
@article{10.1145/3495152,
author = {Saileshwar, Gururaj and Boivie, Rick and Chen, Tong and Segal, Benjamin and Buyuktosunoglu, Alper},
title = {HeapCheck: Low-cost Hardware Support for Memory Safety},
year = {2022},
issue_date = {March 2022},
publisher = {Association for Computing Machinery},
address = {New York, NY, USA},
volume = {19},
number = {1},
issn = {1544-3566},
url = {https://doi.org/10.1145/3495152},
doi = {10.1145/3495152},
month = jan,
articleno = {10},
numpages = {24},
keywords = {Memory safety, hardware bounds checking, software security}
}