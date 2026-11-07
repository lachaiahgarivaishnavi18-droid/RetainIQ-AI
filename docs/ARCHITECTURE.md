# RetainIQ architecture

React/Vite → authenticated REST API → SQLAlchemy → SQLite locally / PostgreSQL via Compose.
Feature pipelines and fitted models are stored in a protected runtime directory. Only application-produced Joblib files are loaded; arbitrary model uploads are not supported.

## Data contract

One customer ID identifies one immutable snapshot in a dataset. Existing IDs are rejected so historical model evidence is not silently overwritten. Each import has its own provenance and validation record. Uploads must contain customer_id, total_orders, total_spend, days_since_last_purchase. Other behavior features are optional. churn_label is an observed binary future-window target, not a recency rule. The owner must establish a snapshot cutoff and a subsequent fixed observation window before supplying labels. Never include post-cutoff behavior in feature columns.

CSV mappings are source-column → canonical-column JSON. Unknown and protected columns are ignored and reported. Negative, infinite, nonnumeric, invalid consent, and malformed labels are rejected. Duplicate IDs within an import keep the first row and are counted. Outliers are flagged using IQR; rows are retained. Missing values use a training-fitted median and categorical defaults. Derived features: average order value, return ratio, complaint frequency, engagement score and average purchase interval. Purchase trends and last-interaction recency are not fabricated from a single aggregate snapshot. Transaction records for the synthetic demo reconcile to generated snapshots; uploaded aggregates have no invented transaction histories.

## Evaluation

Four core classifiers are compared. XGBoost is included if installed. Class-balanced logistic/tree/forest and optional XGBoost weighting handle imbalance; no resampling occurs before splitting. Validation PR-AUC selects the model; held-out test scores are computed once for that model. Pipeline transforms are fitted only on training rows. Random splits are stratified 60/20/20. Multiple dated snapshots use chronological boundaries and purge training/validation labels that extend into the next partition; label_observed_at is required for that mode. Repeated snapshots of the same person require a group-aware extension before use: IDs in the present schema represent distinct customers, and re-identified duplicate people across IDs cannot be detected automatically.

SHAP LinearExplainer gives log-odds contributions for logistic regression. TreeExplainer gives raw-model contributions (probability for the random forest, margin for gradient boosting). Signed values are not probability changes across all model types. Global absolute SHAP is computed on up to 80 held-out rows; permutation PR-AUC importance cross-checks the original columns. These describe model associations, not causal reasons for churn. Threshold 0.5 evaluation metrics are distinct from configurable operational bands.

## Agent execution

LangGraph typed state routes profiling → behavior → prediction → explainability → segmentation → strategy → conditional campaign drafting → impact analysis → human approval. Each analytical node invokes schema-validated registry tools and stores invocation arguments and results. SQLite checkpoint files persist graph state across API requests and restarts. Human review resumes with a LangGraph Command; it approves the analytical workflow, independently of campaign approval. Transient HTTP timeouts receive bounded retries. Failures are recorded as failed executions.

Tools are read, analytical or draft operations. Authorization is checked before invocation; there is no arbitrary SQL, shell, or outbound communication tool. Inputs and output envelopes are validated. Analytical tools have bounded dataset sizes and a 90-second response deadline (elapsed-time check, not a force-cancel sandbox); provider calls have transport timeouts and bounded conversation rounds. Multi-process isolation would be required to force-cancel CPU-bound analytical work.

The local assistant is an explicitly labeled keyword tool router, not a simulated LLM. An optional OpenAI-compatible provider receives tool schemas and must retrieve facts. All retrieved evidence is returned beside generated summaries. Provider output remains subject to human review; model prompts cannot guarantee a hallucination-free provider. Customer records must be treated as untrusted content.

## Campaigns and outcomes

RFM business rules provide transparent segmentation. Annualized historical revenue is a proxy, not profit-based probabilistic CLV. Strategies use actual observed complaints, recency, engagement and model attributions. Discounts have explicit spend/discount-dependency checks and still require margin review. Campaign drafts do not send anything. Only reviewers/admins can approve, email audiences must have consent, and outcomes require a campaign member, approved campaign, observation time, cost and evidence. An outcome can be recorded once per campaign/customer. No randomized control model exists, so no causal uplift or estimated retention success is claimed.

## Scope and operating limits

All 52 navigation entries use shared domain workspaces; they are not 52 independent applications. RFM rules are implemented; K-Means and DBSCAN are future alternatives. Role names are constrained strings on users; customer features and explanations use versioned JSON columns rather than separate tables for every conceptual entity. Population mean-shift monitoring is a diagnostic, not a full drift detector. Historical observed churn series, repeated-window quality monitoring, sending providers, consent provenance integrations, asynchronous job queues and causal impact modeling require real deployment data and additional infrastructure. No sensitive demographics are used in predictions or offers. Formal fairness validation requires a governed evaluation dataset.

Local rate limiting is per process. Production needs a shared limiter, TLS, backups, secret rotation, restricted signup, job queues, monitoring, security review, dataset governance and deployment-specific load testing. The development first-admin bootstrap is not safe for a publicly exposed empty database. SQLite graph checkpoints require a single API instance; clustered hosting needs a PostgreSQL checkpoint backend. PostgreSQL application schema support does not make local graph checkpoints distributed.
