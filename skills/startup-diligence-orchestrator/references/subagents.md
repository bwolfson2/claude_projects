# Sub-Agent Design

## Agent Roles

### Intake agent

Own file inventory, category inference, and missing-document detection. Hand off a clean manifest plus a short note on likely high-value files.

### Commercial agent

Assess market size claims, ICP clarity, customer proof, churn and retention evidence, sales efficiency, funnel quality, and competitive positioning.

### Product and technical agent

Assess product maturity, roadmap realism, engineering throughput, architectural risk, security posture, and dependency on key individuals.

### Finance and legal agent

Assess revenue quality, burn and runway, gross margin shape, cap table cleanliness, debt or SAFEs, contract risk, IP ownership, and compliance exposure.

### Memo agent

Merge findings into one narrative. Preserve uncertainty and call out which open questions are still gating.

## Coordination Rules

- Give each agent the dataroom manifest plus only the files relevant to that domain.
- Require every agent to cite evidence with file paths.
- Do not let one agent restate another agent's conclusions without checking the source documents.
- Consolidate duplicated findings into one issue with the strongest evidence set.
