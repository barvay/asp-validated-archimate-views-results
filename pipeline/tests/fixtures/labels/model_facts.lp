% Test model for the labels (asp/gate3/labels.lp).

element("e1", "ApplicationComponent", "Cart & Checkout").
element("e2", "ApplicationInterface", "Café-Überprüfung").
element("e3", "ApplicationService", "Größe prüfen").

relation("r_spec", "Serving", "e1", "e2").
relation("r_plain", "Flow", "e2", "e3").
rel_specialization("r_spec", "feeds").
