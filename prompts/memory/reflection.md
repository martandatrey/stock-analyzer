# Step: Reflection on a past call

You are reviewing one of the team's own past decisions now that the outcome is known. Your lesson will be stored and shown to future analysts of this stock, so every word must earn its place.

## The decision
- Date: {{call_date}}
- Stock: {{ticker}} ({{exchange}}), investor horizon {{horizon}}
- Rating given: **{{rating}}** with confidence {{confidence}}
- Summary at the time: {{call_summary}}

## What happened
- The outcome window covers **{{settle_days}} trading days** from the call. That may be much shorter than the horizon the call was made for.
- Stock return: {{raw_return}}
- {{benchmark}} return: {{benchmark_return}}
- Alpha (stock minus benchmark): {{alpha}}
- Scored as: **{{outcome}}**

## Write
Exactly 2-4 sentences of plain prose: no bullets, no headings.
1. What the return and alpha say about the directional call (cite the figures). Say plainly if the window is too short to judge the thesis.
2. Which part of the original reasoning this window supports or undercuts.
3. One concrete lesson to apply to the next analysis of this stock.

## Output schema
{{output_schema}}
