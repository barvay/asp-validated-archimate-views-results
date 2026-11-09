% Gate 3f: the labels show the model's names, so a vertex or edge with the right id cannot show
% something else. Exact match after the normalisation of scripts/pipeline.py (label_lines).
% Input: model facts (element/3, relation/4, rel_specialization/2) + keep_element/1, keep_relation/1
%        + cell_line/3, edge_label/2 (parsed from 3_view.drawio).
% Band frame labels are checked in bands.lp.

% --- vertex: line 1 is the element name, line 2 its ArchiMate type, nothing else
label_lines(E,N) :- keep_element(E), cell(E,_,_,_,_), N = #count{ K : cell_line(E,K,_) }.
violation("LABEL-MISMATCH", (E,"lines",N,2)) :- label_lines(E,N), N != 2.
violation("LABEL-MISMATCH", (E,"name",G,Name)) :- keep_element(E), element(E,_,Name), cell_line(E,1,G), G != Name.
violation("LABEL-MISMATCH", (E,"type",G,T)) :- keep_element(E), element(E,T,_), cell_line(E,2,G), G != T.

% --- edge: the relation specialization, or the relation type when it has none
has_rel_specialization(R) :- rel_specialization(R,_).
edge_label_expected(R,S) :- rel_specialization(R,S).
edge_label_expected(R,T) :- relation(R,T,_,_), not has_rel_specialization(R).
edge_label_ok(R) :- edge_label(R,L), edge_label_expected(R,L).
violation("LABEL-MISMATCH", (R,"edge",G,L)) :- keep_relation(R), edge_label(R,G), not edge_label_ok(R),
                                               edge_label_expected(R,L).

message("LABEL-MISMATCH", "The label does not show the model's name (id, part, given, expected). A vertex label has exactly two lines, NAME<br><i>TYPE</i>: the element name unchanged as in model_facts.lp, then its ArchiMate type; no other line breaks (draw.io wraps long names itself). An edge label, in the edge's own value attribute, is the relation specialization, or the relation type if it has none.").
