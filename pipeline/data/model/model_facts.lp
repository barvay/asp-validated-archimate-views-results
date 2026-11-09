% Model facts exported from model.archimate (model: Web Shop (example)) by scripts/export_facts.py.
% Schema: docs/fact-schema.md. Ids are the Archi XML ids. Do not edit by hand.
% 17 elements, 22 relations.

% Elements
element("id-371b7e40", "Node", "Application Server").
element("id-4a21d48a", "BusinessRole", "Shopper").
element("id-5042d146", "ApplicationComponent", "Web Shop").
element("id-56f9b95e", "ApplicationInterface", "Payment API").
element("id-703e898f", "DataObject", "Order Record").
element("id-7a992b77", "SystemSoftware", "Database Engine").
element("id-7ef65dc2", "Node", "Database Server").
element("id-9120580e", "Grouping", "Payment Domain").
element("id-9da8f1fa", "BusinessProcess", "Place Order").
element("id-a22c81f9", "ApplicationComponent", "Inventory Service").
element("id-b39f008e", "BusinessActor", "Customer").
element("id-b8f37eb5", "BusinessProcess", "Fulfil Order").
element("id-bfc95e50", "ApplicationComponent", "Payment Service").
element("id-cce55e43", "BusinessObject", "Order").
element("id-d5491e7e", "ApplicationService", "Checkout").
element("id-f1c19a73", "Requirement", "Fast Checkout").
element("id-f2e18ffc", "SystemSoftware", "Shop Runtime").

% Element specializations
specialization("id-5042d146", "storefront").
specialization("id-bfc95e50", "payment_provider").

% Relations
relation("id-1548fffa", "Serving", "id-f2e18ffc", "id-bfc95e50").
relation("id-2e1913da", "Assignment", "id-4a21d48a", "id-9da8f1fa").
relation("id-3e4f80a1", "Aggregation", "id-9120580e", "id-56f9b95e").
relation("id-42eaa789", "Flow", "id-5042d146", "id-a22c81f9").
relation("id-456bcd04", "Access", "id-5042d146", "id-703e898f").
relation("id-46bc5733", "Composition", "id-371b7e40", "id-f2e18ffc").
relation("id-5b3e1c83", "Triggering", "id-9da8f1fa", "id-b8f37eb5").
relation("id-6175e2d9", "Serving", "id-56f9b95e", "id-5042d146").
relation("id-6502b8d9", "Assignment", "id-b39f008e", "id-4a21d48a").
relation("id-6adf0eb8", "Serving", "id-f2e18ffc", "id-5042d146").
relation("id-6f7aae63", "Association", "id-bfc95e50", "id-a22c81f9").
relation("id-8e1ddbdf", "Flow", "id-371b7e40", "id-7ef65dc2").
relation("id-9b671acf", "Access", "id-9da8f1fa", "id-cce55e43").
relation("id-a20b9975", "Access", "id-a22c81f9", "id-703e898f").
relation("id-b12874ba", "Flow", "id-5042d146", "id-56f9b95e").
relation("id-bb5e9647", "Access", "id-7a992b77", "id-703e898f").
relation("id-c3545d86", "Serving", "id-d5491e7e", "id-9da8f1fa").
relation("id-d99c208e", "Realization", "id-5042d146", "id-f1c19a73").
relation("id-da3d3170", "Aggregation", "id-9120580e", "id-bfc95e50").
relation("id-e44347c9", "Composition", "id-7ef65dc2", "id-7a992b77").
relation("id-e691334f", "Composition", "id-bfc95e50", "id-56f9b95e").
relation("id-e8a5bcbc", "Realization", "id-5042d146", "id-d5491e7e").

% Relation specializations

% Relation attributes
access_type("id-456bcd04", "write").
access_type("id-9b671acf", "readwrite").
access_type("id-a20b9975", "read").
access_type("id-bb5e9647", "readwrite").
directed("id-6f7aae63").

% Properties

% Views: every diagram of the model is a predefined view

view("id-5a6df720", "Checkout overview").
view_documentation("id-5a6df720", "Who takes part in a purchase and which applications serve the checkout.").
view_element("id-5a6df720", "id-4a21d48a").
view_element("id-5a6df720", "id-5042d146").
view_element("id-5a6df720", "id-56f9b95e").
view_element("id-5a6df720", "id-9da8f1fa").
view_element("id-5a6df720", "id-a22c81f9").
view_element("id-5a6df720", "id-b39f008e").
view_element("id-5a6df720", "id-bfc95e50").
view_element("id-5a6df720", "id-d5491e7e").
view_relation("id-5a6df720", "id-2e1913da").
view_relation("id-5a6df720", "id-42eaa789").
view_relation("id-5a6df720", "id-6175e2d9").
view_relation("id-5a6df720", "id-6502b8d9").
view_relation("id-5a6df720", "id-c3545d86").
view_relation("id-5a6df720", "id-e691334f").
view_relation("id-5a6df720", "id-e8a5bcbc").
view_inside("id-5a6df720", "id-56f9b95e", "id-bfc95e50").

view("id-a1047eab", "Deployment").
view_documentation("id-a1047eab", "Which nodes run which software.").
view_element("id-a1047eab", "id-371b7e40").
view_element("id-a1047eab", "id-7a992b77").
view_element("id-a1047eab", "id-7ef65dc2").
view_element("id-a1047eab", "id-f2e18ffc").
view_relation("id-a1047eab", "id-46bc5733").
view_relation("id-a1047eab", "id-8e1ddbdf").
view_relation("id-a1047eab", "id-e44347c9").
view_inside("id-a1047eab", "id-7a992b77", "id-7ef65dc2").
view_inside("id-a1047eab", "id-f2e18ffc", "id-371b7e40").
