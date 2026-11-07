export const sections = [
  {name:'Dashboard', icon:'overview', pages:['Executive Overview','Customer Retention Dashboard','Churn Risk Overview','Business Performance']},
  {name:'Customer Management', icon:'customers', pages:['Customer Directory','Customer Profile','Customer Transaction History','Customer Behavior Analysis','Customer Segmentation','Customer Lifetime Value']},
  {name:'Churn Prediction', icon:'risk', pages:['Churn Prediction Dashboard','Individual Customer Prediction','Batch Churn Prediction','Churn Risk Classification','High-Risk Customers','Churn Trend Analysis','Model Performance']},
  {name:'Explainable AI', icon:'explain', pages:['Global Feature Importance','SHAP Summary Analysis','Individual Customer Explanation','Churn Reason Explorer','Model Explainability Reports']},
  {name:'Multi-Agent Intelligence', icon:'agents', pages:['AI Agent Dashboard','Customer Profiling Agent','Churn Prediction Agent','Behavior Analysis Agent','Explainability Agent','Customer Segmentation Agent','Retention Strategy Agent','Campaign Recommendation Agent','Impact Analysis Agent','Orchestrator Agent','Agent Execution Logs']},
  {name:'Retention Management', icon:'retention', pages:['Retention Strategy Dashboard','Personalized Retention Strategies','Next Best Action','Offer Recommendation','Retention Campaign Management','Campaign Performance']},
  {name:'LLM Intelligence', icon:'assistant', pages:['Retail AI Assistant','Natural Language Analytics','Customer Insight Generation','Business Recommendations']},
  {name:'Reports and Administration', icon:'settings', pages:['Customer Reports','Churn Prediction Reports','Retention Reports','Data Import','Model Configuration','LLM Configuration','User Management','Audit Logs','System Settings']},
]
export const slug = (name:string) => name.toLowerCase().replace(/[^a-z0-9]+/g,'-')
export const allPages = sections.flatMap(section=>section.pages)
