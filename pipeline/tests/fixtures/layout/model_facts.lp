% Test model for the gate 2 layout rules (IMPLIED-CYCLE, frames of `other` elements).

element("x", "BusinessActor", "X").
element("p", "ApplicationComponent", "P (container)").
element("q", "ApplicationComponent", "Q (container)").
element("a", "ApplicationComponent", "A").
element("b", "ApplicationComponent", "B").
element("c", "ApplicationComponent", "C").
element("t", "Node", "T").
element("g", "Grouping", "G").
element("d", "ApplicationComponent", "D (no relation to P)").

% Relations behind the nestings of the tests (container -> member).
relation("r_pa", "Composition", "p", "a").
relation("r_pb", "Aggregation", "p", "b").
relation("r_qb", "Composition", "q", "b").
relation("r_qp", "Composition", "q", "p").
relation("r_pg", "Aggregation", "p", "g").
relation("r_pc", "Serving", "p", "c").
relation("r_ca", "Composition", "c", "a").
relation("r_pd", "Composition", "p", "d").
