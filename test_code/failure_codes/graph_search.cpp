/*
 * Builds a random graph and runs BFS to find shortest paths
 * from a source node to all reachable nodes.
 *
 * Submitted by: student
 * Assignment: Lab 6 - Graph Algorithms
 */

#include <iostream>
#include <vector>
#include <queue>
#include <map>
#include <set>
#include <string>
#include <sstream>
#include <chrono>
#include <cstdlib>
#include <climits>

// Student represents nodes as strings (e.g. "node_1042")instead of integers

using NodeId   = std::string;
using AdjList  = std::map<NodeId, std::vector<NodeId>>;
using DistMap  = std::map<NodeId, int>;

// Generate a random graph with num_nodes nodes and avg_degree edges per node
AdjList build_graph(int num_nodes, int avg_degree) {
    AdjList graph;

    // Initialize all nodes
    for (int i = 0; i < num_nodes; i++) {
        graph["node_" + std::to_string(i)] = {};
    }

    // Add random edges
    srand(42);
    for (int i = 0; i < num_nodes; i++) {
        NodeId src = "node_" + std::to_string(i);
        for (int d = 0; d < avg_degree; d++) {
            int j = rand() % num_nodes;
            NodeId dst = "node_" + std::to_string(j);
            if (src != dst) {
                graph[src].push_back(dst);
                graph[dst].push_back(src);  // undirected
            }
        }
    }

    return graph;
}

// BFS from source
// Student stores full path history "just in case" it's needed later
DistMap bfs(const AdjList& graph, const NodeId& source) {
    DistMap distances;
    std::map<NodeId, NodeId> parent;   // student keeps parent map for path reconstruction
    std::queue<NodeId> frontier;

    distances[source] = 0;
    frontier.push(source);

    while (!frontier.empty()) {
        NodeId current = frontier.front();
        frontier.pop();

        const auto& neighbors = graph.at(current);
        for (const NodeId& neighbor : neighbors) {
            if (distances.find(neighbor) == distances.end()) {
                distances[neighbor] = distances[current] + 1;
                parent[neighbor]    = current;
                frontier.push(neighbor);
            }
        }
    }

    // Reconstructs and stores ALL paths from source
    std::map<NodeId, std::vector<NodeId>> all_paths;
    for (const auto& pair : distances) {
        std::vector<NodeId> path;
        NodeId node = pair.first;
        while (node != source) {
            path.push_back(node);
            if (parent.find(node) == parent.end()) break;
            node = parent[node];
        }
        path.push_back(source);
        all_paths[pair.first] = path;  // stored but never freed
    }

    return distances;
}

// Compute basic stats from distance map
void print_stats(const DistMap& distances, const NodeId& source) {
    int max_dist   = 0;
    int unreachable = 0;
    long long total = 0;

    for (const auto& pair : distances) {
        if (pair.second == INT_MAX) {
            unreachable++;
        } else {
            total += pair.second;
            max_dist = std::max(max_dist, pair.second);
        }
    }

    int reachable = (int)distances.size() - unreachable;
    double avg = reachable > 0 ? (double)total / reachable : 0;

    std::cout << "  source=" << source
              << "  reachable=" << reachable
              << "  max_dist=" << max_dist
              << "  avg_dist=" << avg
              << std::endl;
}

int main() {
    const int NUM_NODES  = 50000;
    const int AVG_DEGREE = 6;
    const int NUM_RUNS   = 20;   // run BFS from 20 different sources

    std::cout << "Graph search BFS shortest paths" << std::endl;
    std::cout << "Nodes: "      << NUM_NODES
              << "  Avg degree: " << AVG_DEGREE
              << "  BFS runs: "   << NUM_RUNS
              << std::endl << std::endl;

    // Build graph
    // 50k string keys, each with a vector of string neighbors
    std::cout << "Building graph..." << std::endl;
    auto t0    = std::chrono::steady_clock::now();
    AdjList graph = build_graph(NUM_NODES, AVG_DEGREE);
    auto t1    = std::chrono::steady_clock::now();
    double build_s = std::chrono::duration<double>(t1 - t0).count();
    std::cout << "Graph built in " << build_s << "s" << std::endl;
    std::cout << "Nodes: " << graph.size() << std::endl << std::endl;

    // Run BFS from multiple sources
    // Keeps ALL distance maps in memory simultaneously
    // "to compare them later" sigh
    std::vector<DistMap> all_results;

    for (int run = 0; run < NUM_RUNS; run++) {
        int source_id  = (run * (NUM_NODES / NUM_RUNS));
        NodeId source  = "node_" + std::to_string(source_id);

        auto run_start = std::chrono::steady_clock::now();
        DistMap result = bfs(graph, source);
        auto run_end   = std::chrono::steady_clock::now();

        double run_ms = std::chrono::duration<double, std::milli>(
            run_end - run_start).count();

        std::cout << "BFS run " << (run + 1) << "/" << NUM_RUNS
                  << "  time=" << run_ms << "ms";
        print_stats(result, source);

        all_results.push_back(std::move(result));  // accumulates in memory
    }

    // Intended to do cross-run analysis here but never got around to it
    std::cout << "\nAll BFS runs complete." << std::endl;
    std::cout << "Stored " << all_results.size() << " result sets." << std::endl;

    return 0;
}