# jev-drone site

The project page for [jev-drone](https://github.com/RomanSlack/jev-drone). Next.js App Router, plain CSS, no UI library. Design decisions live in `DESIGN.md`.

```bash
npm install
npm run dev          # http://localhost:3000
npm run build
```

Set `NEXT_PUBLIC_SITE_URL` to the production URL before building. It drives the canonical tag, Open Graph URLs, `robots.txt`, `sitemap.xml` and the JSON-LD. On Vercel, set the project root directory to `site/`.

`data/flight.json` (trajectory, gate position, one real judgment) is exported from `course.mp4.tape.npy`, the tape of the recorded 65 s run. The figures in `public/figures/` are frames from that same run.
