# hwp-agent PoC

LLM-based Korean public document generator targeting HWPX format.

## Goal
Text input → properly formatted `.hwpx` (표, 단, 레이아웃 포함)

## Structure
```
data/samples/   # sample .hwpx files (gitignored)
src/            # core code
notebooks/      # experiments
```

## PoC Steps
1. Analyze HWPX XML structure
2. Prompt LLM to generate valid HWPX XML
3. Validate output
4. SFT on public document corpus
