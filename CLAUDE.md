# CLAUDE.md

Christmas gift lottery (Secret Santa) — a small Nuxt 3 app. It randomly pairs each participant with someone to buy a gift for, emails each participant their pick via EmailJS, and lets a user type their name to see who they drew. UI text is mostly Polish.

## Commands

Dependencies are installed with **yarn** (`node_modules/.yarn-integrity` exists). The repo also contains `package-lock.json`, so don't mix the two package managers.

```bash
yarn install        # install deps (runs `nuxt prepare` via postinstall, which generates .nuxt/)
yarn dev            # dev server at http://localhost:3000 (the app lives at /login)
yarn build          # production build -> .output/
yarn preview        # serve the production build locally
yarn generate       # static site generation
npx nuxi typecheck  # type check (needs vue-tsc + typescript installed; they aren't deps yet)
```

There are no tests, linters or formatters set up.

## Structure

- [nuxt.config.ts](nuxt.config.ts): uses only the `@nuxt/ui` module (Tailwind-based `U*` components such as `UButton`, `UModal`, `UCard`, `UForm`).
- [app.vue](app.vue): `<NuxtLayout><NuxtPage/></NuxtLayout>`, so [layouts/default.vue](layouts/default.vue) (a card with the title and a `<slot />`) wraps every page.
- [pages/index.vue](pages/index.vue): redirects `/` to `/login`.
- [pages/login/index.vue](pages/login/index.vue): the only real page. It holds all the app logic:
  - "Start lottery" opens a confirmation modal. Confirming ("Tak") runs `draw(participantsList)`, then `sendResults` sends one EmailJS email per entry in `participantEmails`, adding a `chosen` field. Entries with no draw result are skipped with a warning.
  - The name form calls `showResults(results, name)` and shows the pick in a modal.
  - The EmailJS service ID, template ID and public key are hardcoded in `sendEmail`. The template expects the fields `name`, `email` and `chosen`.
  - Script imports use the `~/script/...` alias.
- [script/draw.js](script/draw.js): the pairing algorithm. It shuffles the receivers until nobody gets themselves, and returns `[{ "Giver": "Receiver" }, ...]` (or `[]` with fewer than 2 participants). It has no side effects.
- [script/drawResults.js](script/drawResults.js): looks up a giver's pick in the draw results.
- [assets/participants.json](assets/participants.json): the participant data:
  - `participantsList`: names used in the draw.
  - `participantEmails`: `{name, email}` entries that get emails. Names should match `participantsList`.
  - `emailList`: unused.
- `server/`: only a `tsconfig.json`; there are no API routes.

## Known issues / gotchas

- Draw results live only in component state, with no backend or persistence. The name lookup works only in the same page session that ran the draw (a reload loses it).
- `participants.json` contains real names and email addresses. Treat it as personal data.
- Confirming the lottery sends real emails right away, so avoid it while developing unless that's intended.
- The local `node_modules` was last seen with Nuxt 2.15.8, which is stale (package.json asks for Nuxt ^3.14). Run `yarn install` before `yarn dev` or `yarn build`, otherwise they fail with `Cannot find module 'nuxt/config'`.
