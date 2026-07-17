# Asset Class Rules

`x-fetch` assigns each post to exactly one asset class using simple keyword scoring.

## Categories

- `crypto`
- `us-stocks`
- `a-shares`
- `macro`
- `ai`
- `other`

## Intent

These rules are deliberately lightweight. They are meant to be fast and cheap, not perfect. The output should be stable enough for daily monitoring and easy to refine later.

## Priority

The classifier scores all categories and picks the highest score. If scores tie, use this tie-break order:

1. `crypto`
2. `us-stocks`
3. `a-shares`
4. `macro`
5. `ai`
6. `other`

## Practical Examples

- BTC / ETH / Solana / meme coin discussion -> `crypto`
- 纳指 / 标普 / 美股财报 / 芯片股 -> `us-stocks`
- A股 / 沪深 / 创业板 / 科创板 -> `a-shares`
- Fed / CPI / 利率 / 汇率 / 国债收益率 -> `macro`
- 大模型 / inference / GPU / OpenAI / agent -> `ai`

If nothing meaningful matches, classify as `other`.
