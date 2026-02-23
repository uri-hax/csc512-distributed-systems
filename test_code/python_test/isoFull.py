import networkx as nx

G1 = nx.Graph()
G2 = nx.Graph()
a, b, c, d, e, f, g, h = 9, 10, 11, 12, 13, 14, 15, 16

G1.add_edges_from([
    (a, b), (a, c), (a, d), (a, h), (b, c), (b, f), (b, g), (c, d), (c, e), (d, e), (d, h), (e, f), (e, g), (f, g), (f, h), (g, h)
])

G2.add_edges_from([
    (1, 2), (1, 6), (1, 3), (1, 4), (2, 3), (2, 8), (2, 4), (3, 5), (3, 7), (4, 5), (4, 8), (5, 6), (5, 8), (6, 7), (6, 8), (7, 8)
])

is_isomorphic = nx.is_isomorphic(G1, G2)

if is_isomorphic:
    print ('True')
else:
    print ('False')
