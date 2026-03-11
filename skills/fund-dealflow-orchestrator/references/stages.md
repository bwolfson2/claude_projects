# Stage Definitions

## Pipeline Stages

- `sourced`
  - Company exists in the registry.
  - No substantive interaction yet.
- `screening`
  - Basic thesis formed.
  - First call or data request is being arranged.
- `first_meeting`
  - Intro call completed.
  - A go/no-go decision on deeper work is pending.
- `watchlist`
  - Not active now, but worth monitoring.
- `dataroom_requested`
  - The fund wants diligence materials.
- `dataroom_received`
  - Materials are in hand and intake is pending.
- `deep_diligence`
  - Specialist diligence work is running.
- `ic_prep`
  - Diligence is synthesized enough for an IC note.
- `term_sheet`
  - The fund is actively negotiating or issuing terms.
- `closed_invested`
  - Investment completed.
- `closed_passed`
  - The fund passed.
- `portfolio_monitoring`
  - Company is invested and being tracked post-close.

## Exit Criteria

- Do not leave `first_meeting` without a clear next action.
- Do not leave `dataroom_received` without either starting diligence or explicitly parking the deal.
- Do not leave `deep_diligence` without:
  - a recommendation
  - a risk list
  - open questions or cleanup items
- Do not move to `term_sheet` unless the decision posture is clearly positive.
- Do not mark `closed_invested` without a dated decision record.
