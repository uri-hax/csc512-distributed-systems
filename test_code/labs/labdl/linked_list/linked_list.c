#include "linked_list.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/**
 * In this file, you will find the partial implementation of common doubly
 * linked list functions.
 *
 * Your first task is to debug some of the functions!
 *
 * After you have found all of the bugs, you will be writing three doubly
 * linked list functions and test them.
 *
 */

/**
 * find and return the length of the list
 *
 * given a pointer to the head of list
 */
int length_list(node_t* head_list) {
  int len = 0;
  if (!head_list) {
    return len;
  }
  node_t* current = head_list;
  while (current) {
    len++;
    current = current->next; 
  }
  free(current);
  return len;
}


/**
 * returns the value of the head of the list
 *
 * given pointer to the head of the list
 */
void* get_first(node_t* head_list) { 
  if (!head_list) { 
      return NULL; 
  }
  return head_list->data; 
}


/** returns the value of the last element of the list
 *
 * given a pointer to the head of the list
 */
void* get_last(node_t* head_list) {
  if (!head_list) {
    printf("get_last: List is empty\n");
    return NULL;
  }
  
  node_t* curr = head_list;
  while (curr) {  
    printf("get_last: Visiting node at %p\n", (void*)curr);  // Debug output
    
    if (!curr->next) {  
      printf("get_last: Last node found at %p\n", (void*)curr);
      return curr->data;
    }

    if ((uintptr_t)curr->next < 0x1000) {  
      printf("get_last: Detected invalid pointer!\n");
      return NULL;
    }

    curr = curr->next;
  }

  printf("get_last: Unexpected end of function\n");
  return NULL;
}




/** TODO: implement this!
 * inserts element at the beginning of the list
 *
 * given a pointer to the head of the list, a void pointer representing the
 * value to be added, and the size of the data pointed to
 *
 * returns nothing
 */
void insert_first(node_t** head_list, void* to_add, size_t size) {
  if (!to_add) return;

  node_t* new_element = (node_t*)malloc(sizeof(node_t));
  void* new_data = malloc(size);
  memcpy(new_data, to_add, size);
  new_element->data = new_data;

  new_element->next = *head_list;
  new_element->prev = NULL;

  if (*head_list) {
    (*head_list)->prev = new_element;
  }

  *head_list = new_element;
}


/**
 * inserts element at the end of the linked list
 *
 * given a pointer to the head of the list, a void pointer representing the
 * value to be added, and the size of the data pointed to
 *
 * returns nothing
 */
void insert_last(node_t** head_list, void* to_add, size_t size) {
  if (!to_add) return;

  node_t* new_element = (node_t*)malloc(sizeof(node_t));
  void* new_data = malloc(size);
  memcpy(new_data, to_add, size);
  new_element->data = new_data;
  new_element->next = NULL;

  printf("insert_last: Adding new node at %p with data at %p\n", (void*)new_element, new_data);

  if (!(*head_list)) {  // List is empty
    *head_list = new_element;
    new_element->prev = NULL;
    printf("insert_last: New head is now %p\n", (void*)*head_list);
    return;
  }

  node_t* curr = *head_list;
  while (curr->next) {
    curr = curr->next;
  }

  curr->next = new_element;
  new_element->prev = curr;

  printf("insert_last: Node %p added after %p\n", (void*)new_element, (void*)curr);
}


/** TODO: implement this!
 * gets the element from the linked list
 *
 * given a pointer to the head of the list and an index into the linked list
 * you need to check to see if the index is out of bounds (negative or longer
 * than linked list)
 *
 * returns the string associated with an index into the linked list
 */
void* get(node_t* head_list, int index) {
  if (!head_list || index < 0) return NULL;

  node_t* curr = head_list;
  int i = 0;

  while (curr) {
    if (i == index) {
      return curr->data;
    }
    curr = curr->next;
    i++;
  }

  return NULL;  // If index is out of bounds
}


/**
 * removes element from linked list
 *
 * given a pointer to the head of list, a void pointer of the node to remove
 * you need to account for if the void pointer doesn't exist in the linked list
 *
 * returns 1 on success and 0 on failure of removing an element from the linked
 * list
 */
int remove_element(node_t **head_list, void *to_remove, size_t size) {
  if (!(*head_list)) return 0;  // element doesn't exist

  node_t* curr = *head_list;

  while (curr) {
    if (!memcmp(curr->data, to_remove, size)) {  // found the element to remove
      printf("remove_element: Removing node at %p\n", (void*)curr);
      
      if (curr->next) {
        curr->next->prev = curr->prev;
      }
      if (curr == *head_list) {
        printf("remove_element: Updating head to %p\n", (void*)curr->next);
        *head_list = curr->next;
      } else {
        printf("remove_element: Updating %p->next to %p\n", (void*)curr->prev, (void*)curr->next);
        curr->prev->next = curr->next;
      }

      free(curr->data);
      free(curr);

      return 1;
    }
    curr = curr->next;
  }

  return 0;
}


/**
 * reverses the list given a double pointer to the first element
 *
 * returns nothing
 */
void reverse_helper(node_t** head_list) {
  if (!head_list || !(*head_list)) return; // Ensure list is valid

  node_t* curr = *head_list;
  node_t* placeholder = NULL;

  printf("reverse_helper: Reversing list starting from %p\n", (void*)curr); // Debug print

  while (curr) {
    if (!curr->next) {
      *head_list = curr;
    }

    node_t* next_node = curr->next;
    curr->next = placeholder;
    curr->prev = next_node; 
    placeholder = curr;
    curr = next_node;
  }

  printf("reverse_helper: Reversal complete. New head is %p\n", (void*)*head_list);
}



/**
 * calls a helper function that reverses the linked list
 *
 * given a pointer to the first element
 *
 * returns nothing
 */
void reverse(node_t** head_list) {
  if (head_list) {
    reverse_helper(head_list);
  }
}

/**
 * removes the first element of the linked list if it exists
 *
 * given a pointer to the head of the linked list
 *
 * returns the void pointer of the element removed
 *
 */
void* remove_first(node_t** head_list) {
  if (!(*head_list)) return NULL;

  node_t* curr = *head_list;
  void* data = curr->data;  

  printf("remove_first: Removing node at %p\n", (void*)curr);

  *head_list = (*head_list)->next;
  if (*head_list) {
    printf("remove_first: New head is now %p\n", (void*)*head_list);
    (*head_list)->prev = NULL;
  } else {
    printf("remove_first: List is now empty\n");
  }

  free(curr);  
  return data;  
}



/** TODO: implement this!
 * removes the last element of the linked list if it exists
 *
 * given a pointer to the head of the linked list
 *
 * returns the void pointer of the element removed
 *
 */
void* remove_last(node_t** head_list) {
  if (!head_list || !(*head_list)) return NULL;

  node_t* curr = *head_list;

  // If only one element exists, update head to NULL
  if (!curr->next) {
    printf("remove_last: Removing last node %p\n", (void*)curr);
    void* data = curr->data;
    free(curr);
    *head_list = NULL;
    return data;
  }

  // Traverse to last node
  while (curr->next) {
    curr = curr->next;
  }

  printf("remove_last: Removing last node %p\n", (void*)curr);
  void* data = curr->data;

  // Ensure we aren't breaking the list
  if (curr->prev) {
    printf("remove_last: Updating previous node %p next to NULL\n", (void*)curr->prev);
    curr->prev->next = NULL;
  }

  free(curr);

  return data;
}

