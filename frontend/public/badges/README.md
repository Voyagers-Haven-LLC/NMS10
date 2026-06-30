# Milestone badge art

Two WebP files per milestone — a grey **silhouette** for the locked state and the
full **illustrated badge** for the completed state. The card swaps between them in
JS (`MilestoneBadge` / `RewardBadge` in `frontend/src/pages/Expedition.jsx`).

| Completed art | Locked silhouette | Card |
|---------------|-------------------|------|
| `badge-01.webp` | `badge-01-locked.webp` | Answer the Call |
| `badge-02.webp` | `badge-02-locked.webp` | Echoes Across the Stars |
| `badge-03.webp` | `badge-03-locked.webp` | Honour the Symbol |
| `badge-04.webp` | `badge-04-locked.webp` | A Universe Remembered |
| `badge-05.webp` | `badge-05-locked.webp` | Rendezvous with Travellers |
| `badge-06.webp` | `badge-06-locked.webp` | Constellations of Community |
| `badge-07.webp` | `badge-07-locked.webp` | A Tribute Among the Stars |
| `badge-08.webp` | `badge-08-locked.webp` | Voices of the Dreamers |
| `reward.webp`   | `reward-locked.webp`   | Final Reward — Dreaming Traveller Card (unlocks at 8/8) |

- **Locked** = the silhouette is shown as-is. **Completed** = the full badge + a
  gold drop-shadow glow (CSS `.milestone-card.completed` / `.reward-card.unlocked`).
- Sizing/glow/brightness: `.milestone-badge` / `.reward-badge` in `frontend/src/styles/v9.css`.

## Source + regenerating

Originals are in `OneDrive/Pictures/PSD Milestone N {Grayed Out|Muted}.png`
(Grayed Out → completed, Muted → locked silhouette). The 3000×3000 PNGs were
downsized to 512px WebP (q85) for the web — ~20 MB → ~0.34 MB. To regenerate
after new art drops, copy the PNGs in and re-run the resize step (Pillow:
`Image.open(p).convert('RGBA').resize(<=512).save(out,'WEBP',quality=85,method=6)`).
