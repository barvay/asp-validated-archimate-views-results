% Gate 3a: the drawio diagram contains exactly the filtered items.
% Input: model facts + keep_element/1, keep_relation/1 + facts parsed from 3_view.drawio:
%   cell(Id, X, Y, W, H)   vertex with absolute integer coordinates
%   edge(Id, Source, Target)
%   duplicate_id(Id)

has_cell(E) :- cell(E,_,_,_,_).
has_edge(R) :- edge(R,_,_).

violation("MISSING-CELL", (E,)) :- keep_element(E), not has_cell(E).
message("MISSING-CELL", "Kept element has no vertex in the diagram (the vertex id must be the element id).").

violation("EXTRA-CELL", (C,)) :- has_cell(C), not keep_element(C), not frame_cell(C).
message("EXTRA-CELL", "Vertex id is not a kept element or a band frame. Draw only kept elements, with their element id as cell id, and the band frames.").

violation("DUPLICATE-ID", (C,)) :- duplicate_id(C).
message("DUPLICATE-ID", "The same cell id is used more than once.").

violation("MISSING-EDGE", (R,)) :- keep_relation(R), not has_edge(R), not nested_relation(R).
message("MISSING-EDGE", "Kept relation has no edge in the diagram (the edge id must be the relation id).").

violation("EXTRA-EDGE", (R,)) :- has_edge(R), not keep_relation(R).
message("EXTRA-EDGE", "Edge id is not a kept relation.").

violation("WRONG-EDGE-ENDS", (R,S,T)) :- edge(R,S,T), keep_relation(R), relation(R,_,S0,T0), (S,T) != (S0,T0).
message("WRONG-EDGE-ENDS", "Edge source/target do not match the relation's source and target in the model (edge, given source, given target).").

violation("ZERO-SIZE", (C,)) :- cell(C,_,_,W,H), W <= 0.
violation("ZERO-SIZE", (C,)) :- cell(C,_,_,W,H), H <= 0.
message("ZERO-SIZE", "Vertex has no positive width and height.").
