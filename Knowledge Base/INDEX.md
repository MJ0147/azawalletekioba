# EKIOBA Knowledge Base

Reference material collected from the EKIOBA workspace.

Iyobo, the AI assistant (xAI Grok), uses this folder as its main source. It indexes every `.md` and `.json` file here **except the ones marked *not indexed* below** — infrastructure notes and documents written for whoever builds EKIOBA rather than for a visitor, this index among them (change this with `KNOWLEDGE_BASE_EXCLUDE`). It uses web search only to fill gaps, and judges what it finds there against this material before any of it reaches a visitor. Edits take effect when the assistant restarts.

This folder is Iyobo's own knowledge and its yardstick for the web — it is not a thing visitors are told about. Iyobo never names it, quotes a file name or shows a `[KB1]` label in a reply, so write these pages in wording it can say out loud.

The website's chat also answers from this folder when the AI assistant is offline. It reads a copy in `frontend/knowledge_base/`, so after editing anything here run `python scripts/sync_knowledge_base.py` and commit the updated copy. CI fails if the copy is out of date.

## EKIOBA Platform

- [Platform guide](EKIOBA%20Platform/platform-guide.md): how the site works — the store, cart and IDIA Coin checkout, wallets, the dashboard, Academy, museum, hotels, cargo, returns and support.

## Documents — *not indexed* by Iyobo

Internal notes. Iyobo must never quote these to a visitor.

- [Project overview](README.md): workspace purpose, local development, and CI/CD model.
- [This index](INDEX.md): the map of this folder, for whoever maintains it.
- [Security architecture](SECURITY.md): authentication, secrets management, database, and hardening guidance.
- [Deployment guide](DEPLOYMENT.md): Supabase platform, Postgres connection, Edge Function limits, workflows, and blockchain integration.
- [Wallet dashboard integration](WALLET_DASHBOARD_INTEGRATION.md): wallet, forecast APIs, frontend charts, configuration, and testing.
- [Supabase schema](Supabase/): SQL for the orders, todos, and Edo vocabulary tables, and Iyobo's private memory and knowledge review queue (`004_iyobo_memory.sql`).
- [Master agent instructions](AGENT_INSTRUCTIONS.md): multi-role assistant spec — Screen Reader, Task Manager, Personal Shopper, Search Machine, Bots Predator & Monitor, Prediction Expert — with operating principles, per-role knowledge bases, architecture, and example flows.

## Language Academy

- [Edo adjectives and adjectival verbs](Language%20Academy/edo-adjectives-grammar.md): grammar reference transcribed from a scanned linguistics paper — adjectival verbs, past-tense inflection, nominalization, relative clauses, and ideophonic qualifiers.
- [Edo adjectives dataset](Language%20Academy/edo-adjectives-dataset.json): the same material as structured JSON, including an `academy_vocabulary` array in the Language Academy's own schema.
- [Edo animal vocabulary](Language%20Academy/edo-animals-vocabulary.md): names of domestic animals and livestock, wild animals, birds and reptiles, with notes on forms to check.
- [Edo animals dataset](Language%20Academy/edo-animals-dataset.json): the same list as JSON, grouped, plus an `academy_vocabulary` array (category `animal`).
- [Edo alphabet](Language%20Academy/edo-alphabet-and-numbers.md): the alphabet letter by letter, with a sound-alike word, an Edo example and its meaning.
- [Edo alphabet dataset](Language%20Academy/edo-alphabet-dataset.json): the alphabet as JSON, plus an `academy_vocabulary` array of the 30 words not already listed.
- [Edo numbers 1–100](Language%20Academy/edo-numbers.md): counting from one to a hundred, with the patterns that build the numbers in between.
- [Edo numbers dataset](Language%20Academy/edo-numbers-dataset.json): the numbers as JSON, plus an `academy_vocabulary` array.
- [Edo everyday vocabulary](Language%20Academy/edo-everyday-vocabulary.md): family and people, home and school objects, food, sky and time, and phrases such as "What is this?" and "thank you".
- [Edo everyday dataset](Language%20Academy/edo-everyday-dataset.json): the same list as JSON, grouped, plus an `academy_vocabulary` array of the 26 words not already listed.
- [Edo question formation](Language%20Academy/edo-questions-grammar.md): polar questions, the particle *yi*, alternative questions with *ra*, and *de* + NP content questions. Transcribed from OCR text, showing each form as printed alongside its likely reading.
- [Edo questions dataset](Language%20Academy/edo-questions-dataset.json): the numbered examples, a particle summary, and an `academy_vocabulary` array.
- [Edo demonstratives and place words](Language%20Academy/edo-demonstratives-grammar.md): this, that, these, those, here and there, with four worked sentences and the silent ọ — ọni is said ni once it follows its noun. Transcribed from a lesson slide.
- [Edo demonstratives dataset](Language%20Academy/edo-demonstratives-dataset.json): the two tables and the examples as JSON, plus an `academy_vocabulary` array of 16 words.

## Benin History

- [Benin Kingdom overview](Benin%20History/benin-kingdom-overview.md): the kingdom, Queen Idia, bronze casting, the Igue festival and coral regalia.
- [Obas of Benin: Benin Royal Museum catalogue](Benin%20History/benin-obas-museum-catalogue.md): the 38 Obas in the museum, Eweka I to Ewuare II, in reign order and grouped by era. Each has the name, reign and description from his portrait's inscription.

## Component notes — *not indexed* by Iyobo

Developer setup notes.

- [Frontend README](Project%20Readmes/frontend-README.md)
- [Backend README](Project%20Readmes/backend-README.md)

Credential files, generated logs, private keys, and deployment artifacts were intentionally excluded. The documents retain secret names and placeholders where they are needed for operational reference.
