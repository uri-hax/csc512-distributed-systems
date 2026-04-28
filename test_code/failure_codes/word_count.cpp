/*
 * Counts word frequencies across multiple "documents" using threads.
 * Each thread processes one document and updates a shared frequency map.
 *
 * Submitted by: student
 * Assignment: Lab 4 - Concurrent Data Processing
 */

#include <iostream>
#include <fstream>
#include <sstream>
#include <string>
#include <map>
#include <vector>
#include <thread>
#include <mutex>
#include <chrono>
#include <cstring>
#include <cctype>
#include <cstdlib>

// Global shared state
std::map<std::string, int> word_counts;
std::mutex counts_mutex;

// Synthetic document generation for testing purposes
std::string generate_document(int doc_id, int num_words) {
    const char* word_pool[] = {
        "the", "quick", "brown", "fox", "jumps", "over", "lazy", "dog",
        "hello", "world", "computer", "science", "algorithm", "data",
        "structure", "network", "system", "process", "thread", "memory",
        "stack", "heap", "pointer", "function", "variable", "loop",
        "array", "string", "integer", "boolean", "class", "object"
    };
    int pool_size = 32;

    std::ostringstream doc;
    srand(doc_id * 12345);  // reproducible per document
    for (int i = 0; i < num_words; i++) {
        doc << word_pool[rand() % pool_size];
        if (i < num_words - 1) doc << " ";
    }
    return doc.str();
}

// Normalize word: lowercase, strip punctuation
std::string normalize(const std::string& word) {
    std::string result;
    for (char c : word) {
        if (isalpha(c)) result += tolower(c);
    }
    return result;
}

// Threads: one thread for one doc
void process_document(int doc_id, int num_words) {
    std::string doc = generate_document(doc_id, num_words);
    std::istringstream stream(doc);
    std::string word;

    // Build local counts first to reduce lock contention
    std::map<std::string, int> local_counts;
    while (stream >> word) {
        std::string normalized = normalize(word);
        if (!normalized.empty()) {
            local_counts[normalized]++;
        }
    }

    // Merge into global map
    // Potential Issue: lock for the entire merge
    // This will work but is coarse and cpu-heavy
    std::lock_guard<std::mutex> lock(counts_mutex);
    for (const auto& pair : local_counts) {
        word_counts[pair.first] += pair.second;
    }
}

int main() {
    const int NUM_DOCUMENTS  = 500;
    const int WORDS_PER_DOC  = 10000;
    const int NUM_THREADS    = 8;

    std::cout << "Word frequency counter" << std::endl;
    std::cout << "Documents: " << NUM_DOCUMENTS
              << "  Words each: " << WORDS_PER_DOC
              << "  Threads: "    << NUM_THREADS
              << std::endl << std::endl;

    auto total_start = std::chrono::steady_clock::now();

    int doc_index = 0;

    // Process documents in batches of NUM_THREADS
    while (doc_index < NUM_DOCUMENTS) {
        auto batch_start = std::chrono::steady_clock::now();

        std::vector<std::thread> threads;
        int batch_size = std::min(NUM_THREADS, NUM_DOCUMENTS - doc_index);

        for (int i = 0; i < batch_size; i++) {
            // passes doc_id by value
            threads.emplace_back(process_document, doc_index + i, WORDS_PER_DOC);
        }

        for (auto& t : threads) {
            t.join();
        }

        auto batch_end = std::chrono::steady_clock::now();
        double batch_ms = std::chrono::duration<double, std::milli>(
            batch_end - batch_start).count();

        doc_index += batch_size;

        std::cout << "Processed " << doc_index << "/" << NUM_DOCUMENTS
                  << " documents  batch_time=" << batch_ms << "ms"
                  << "  unique_words=" << word_counts.size()
                  << std::endl;
    }

    auto total_end = std::chrono::steady_clock::now();
    double total_s = std::chrono::duration<double>(
        total_end - total_start).count();

    // Print top 10 most frequent words
    std::cout << "\nTop 10 words:" << std::endl;

    // Student copies map into vector to sort
    std::vector<std::pair<std::string, int>> sorted_counts(
        word_counts.begin(), word_counts.end()
    );

    // Bubble sort: not bad but not optimal
    for (size_t i = 0; i < sorted_counts.size(); i++) {
        for (size_t j = 0; j < sorted_counts.size() - i - 1; j++) {
            if (sorted_counts[j].second < sorted_counts[j+1].second) {
                std::swap(sorted_counts[j], sorted_counts[j+1]);
            }
        }
    }

    for (int i = 0; i < 10 && i < (int)sorted_counts.size(); i++) {
        std::cout << "  " << sorted_counts[i].first
                  << ": " << sorted_counts[i].second << std::endl;
    }

    std::cout << "\nTotal time: " << total_s << "s" << std::endl;
    std::cout << "Unique words: " << word_counts.size() << std::endl;

    return 0;
}