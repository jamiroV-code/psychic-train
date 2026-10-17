# T76 screens, 17-10-26

Seeded fixture (routed attention JSON, baskets created through the real API). Widths 375, 768, 1280. Regenerate: `E2E_SHOT_DIR=<dir> pnpm test:e2e e2e/narrative.spec.ts`, then compress.

- `ok-375.png`: two lines, signed change, breadth %, 'covers N of N', membership line, no horizontal scroll; legend is one strip with no divider
- `ok-768.png`: two lines, signed change, breadth %, 'covers N of N', membership line, no horizontal scroll; legend is one strip with no divider
- `ok-1280.png`: two lines, signed change, breadth %, 'covers N of N', membership line, no horizontal scroll; legend is one strip with no divider
- `loading-375.png`: one muted 'Loading' line under the header; selector stays aligned right
- `loading-768.png`: one muted 'Loading' line under the header; selector stays aligned right
- `loading-1280.png`: one muted 'Loading' line under the header; selector stays aligned right
- `error-375.png`: one red line; wraps without clipping at 375
- `error-768.png`: one red line; wraps without clipping at 375
- `error-1280.png`: one red line; wraps without clipping at 375
- `empty-375.png`: ONE line ('No baskets yet' + screener link); no second 'No baskets to rank' line
- `empty-768.png`: ONE line ('No baskets yet' + screener link); no second 'No baskets to rank' line
- `empty-1280.png`: ONE line ('No baskets yet' + screener link); no second 'No baskets to rank' line
- `partial-375.png`: 'no data: Layer2' note; the no-data row shows 'no data' in score, change and breadth (never 0)
- `partial-768.png`: 'no data: Layer2' note; the no-data row shows 'no data' in score, change and breadth (never 0)
- `partial-1280.png`: 'no data: Layer2' note; the no-data row shows 'no data' in score, change and breadth (never 0)
- `ranking-off-375.png`: 'Ranking is off' note; score column reads 'no data'; change and breadth still shown
- `ranking-off-768.png`: 'Ranking is off' note; score column reads 'no data'; change and breadth still shown
- `ranking-off-1280.png`: 'Ranking is off' note; score column reads 'no data'; change and breadth still shown
- `coin-expand-375.png`: coins behind Majors: score, 'n of N sources', raw value right-aligned per source, 'no data' + state when missing
- `coin-expand-768.png`: coins behind Majors: score, 'n of N sources', raw value right-aligned per source, 'no data' + state when missing
- `coin-expand-1280.png`: coins behind Majors: score, 'n of N sources', raw value right-aligned per source, 'no data' + state when missing
- `removal-notice-375.png`: screener after removing ETH; viewport scrolled to the board (the notice itself is visually hidden, see report heading 3)
- `removal-notice-768.png`: screener after removing ETH; viewport scrolled to the board (the notice itself is visually hidden, see report heading 3)
- `removal-notice-1280.png`: screener after removing ETH; viewport scrolled to the board (the notice itself is visually hidden, see report heading 3)
