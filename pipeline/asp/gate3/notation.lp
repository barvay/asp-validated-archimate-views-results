% Gate 3d: every edge is drawn as the ArchiMate 3.x notation of its relation type.
% Input: model facts (relation/4, access_type/2, directed/1) + keep_relation/1
%        + edge/3, edge_style/3 (parsed from 3_view.drawio, only the keys below).
% Styles follow the draw.io ArchiMate 3 palette;
% Influence (not in the palette) is dashed 6 4 with an open arrow.
% Only the keys that carry the notation are checked; routing, labels, colours are free.

% --- draw.io values of a key the style does not set
style_default("startArrow", "none").  style_default("endArrow", "classic").
style_default("startFill", "1").      style_default("endFill", "1").
style_default("dashed", "0").         style_default("dashPattern", "3 3").

given(R,K) :- edge_style(R,K,_).
style(R,K,V) :- edge_style(R,K,V).
style(R,K,V) :- edge(R,_,_), style_default(K,V), not given(R,K).

% --- notation kind of a relation: its type, refined by the access mode and association direction
kind(R,T) :- relation(R,T,_,_), T != "Access", T != "Association".
kind(R,access(M)) :- relation(R,"Access",_,_), access_type(R,M).
kind(R,association(directed)) :- relation(R,"Association",_,_), directed(R).
kind(R,association(undirected)) :- relation(R,"Association",_,_), not directed(R).

% --- notation(Kind, Key, Value). Fill only where the arrow head can be filled; dashPattern only on dashed lines.
notation("Composition","startArrow","diamondThin"). notation("Composition","startFill","1").
notation("Composition","endArrow","none").          notation("Composition","dashed","0").

notation("Aggregation","startArrow","diamondThin"). notation("Aggregation","startFill","0").
notation("Aggregation","endArrow","none").          notation("Aggregation","dashed","0").

notation("Assignment","startArrow","oval").  notation("Assignment","startFill","1").
notation("Assignment","endArrow","block").   notation("Assignment","endFill","1").
notation("Assignment","dashed","0").

notation("Realization","startArrow","none"). notation("Realization","endArrow","block").
notation("Realization","endFill","0").       notation("Realization","dashed","1").
notation("Realization","dashPattern","3 3").

notation("Serving","startArrow","none").     notation("Serving","endArrow","open").
notation("Serving","dashed","0").

notation("Triggering","startArrow","none").  notation("Triggering","endArrow","block").
notation("Triggering","endFill","1").        notation("Triggering","dashed","0").

notation("Flow","startArrow","none").        notation("Flow","endArrow","block").
notation("Flow","endFill","1").              notation("Flow","dashed","1").
notation("Flow","dashPattern","6 4").

notation("Influence","startArrow","none").   notation("Influence","endArrow","open").
notation("Influence","dashed","1").          notation("Influence","dashPattern","6 4").

notation("Specialization","startArrow","none"). notation("Specialization","endArrow","block").
notation("Specialization","endFill","0").       notation("Specialization","dashed","0").

% Access: dotted line; the arrow points in the direction of the data (write: to the object = target).
access_ends("write","none","open").  access_ends("read","open","none").
access_ends("access","none","none"). access_ends("readwrite","open","open").
notation(access(M),"startArrow",S) :- access_ends(M,S,_).
notation(access(M),"endArrow",E)   :- access_ends(M,_,E).
notation(access(M),"dashed","1")   :- access_ends(M,_,_).
notation(access(M),"dashPattern","1 4") :- access_ends(M,_,_).

notation(association(directed),"startArrow","none").   notation(association(directed),"endArrow","openAsync").
notation(association(directed),"dashed","0").
notation(association(undirected),"startArrow","none"). notation(association(undirected),"endArrow","none").
notation(association(undirected),"dashed","0").

% --- check (edge, style key, given value, expected value)
violation("RELATION-NOTATION", (R,K,G,V)) :- keep_relation(R), edge(R,_,_), kind(R,Kd),
                                             notation(Kd,K,V), style(R,K,G), G != V.
message("RELATION-NOTATION", "The edge style does not match the ArchiMate notation of the relation type (edge, style key, given value, expected value). Use the style of the relation type from the drawing conventions.").
