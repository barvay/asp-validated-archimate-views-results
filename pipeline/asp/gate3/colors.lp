% Gate 3g: every element box has the colours of its band. Convention: the Archi
% default layer colours; colour has no formal meaning in ArchiMate.
% Input: band/2 (2_layout.lp) + keep_element/1 + cell/5, cell_style/3 (parsed from 3_view.drawio).
% `other` elements (Grouping, Location, ...) are grey and dashed. The element colours match the band
% frames (bands.lp) but never equal them (tests/test_colors.py).

% --- layer_color(Band, Key, Value)
layer_color(motivation,  "fillColor","#ccccff"). layer_color(motivation,  "strokeColor","#6666cc").
layer_color(business,    "fillColor","#ffffb5"). layer_color(business,    "strokeColor","#b3b300").
layer_color(application, "fillColor","#b5ffff"). layer_color(application, "strokeColor","#00a3a3").
layer_color(technology,  "fillColor","#c9e7b7"). layer_color(technology,  "strokeColor","#5a8f3c").
layer_color(other,       "fillColor","#f5f5f5"). layer_color(other,       "strokeColor","#999999").
layer_color(B,"dashed","0") :- band_rank(B,_).
layer_color(other,"dashed","1").

% --- draw.io values of a key the style does not set
vertex_default("fillColor","#ffffff"). vertex_default("strokeColor","#000000"). vertex_default("dashed","0").
vertex_given(E,K) :- cell_style(E,K,_).
vertex_style(E,K,V) :- cell_style(E,K,V).
vertex_style(E,K,V) :- cell(E,_,_,_,_), vertex_default(K,V), not vertex_given(E,K).

% --- check (element, style key, given value, expected value)
violation("LAYER-COLOR", (E,K,G,V)) :- keep_element(E), band(E,B), layer_color(B,K,V), vertex_style(E,K,G), G != V.
message("LAYER-COLOR", "The box does not have the colours of its band (element, style key, given value, expected value). Use fillColor, strokeColor and dashed of the band from the drawing conventions.").
