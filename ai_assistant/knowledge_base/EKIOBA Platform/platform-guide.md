# EKIOBA Platform Guide

How the EKIOBA website works: the store, cart and IDIA Coin checkout, wallets, the dashboard, the
Academy and museum, hotels, cargo, returns and support.

- **Source.** Mostly collected from the site chat's earlier built-in replies. The hotel list comes
  from the site's own hotel data.
- **Unconfirmed policies.** The returns policy, support response time and contact method have not
  been confirmed; confirm them before relying on them.

---

## Welcome and getting started

Questions this answers: hello, hi, hey, koyo, welcome, getting started, where do I begin.

Koyo, and welcome to EKIOBA, a gateway to Edo and Benin Kingdom culture. Iyobo, EKIOBA's AI cultural
guide, can help with products, IDIA Coin payments, Edo history, the Language Academy, the Benin
Royal Museum, hotels and cargo.

## About Iyobo

Questions this answers: who are you, what is Iyobo, Aza AI, introduce yourself.

Iyobo (also called Aza AI) is EKIOBA's AI cultural assistant. It runs on Grok from xAI and answers
from EKIOBA's own verified material on Edo language, Benin history and the platform. It searches the
web only to fill gaps, and what it finds there is measured against that material before you see it:
anything the material contradicts is dropped, and anything the material doesn't cover is given to
you as unconfirmed. It can help you shop, check out, learn Edo, book hotels, ship cargo and explore
the heritage behind EKIOBA products.

## Memory and privacy

Questions this answers: do you remember me, remember, memory, forget me, delete my data, privacy,
cookie, teach Iyobo, suggest a word.

Iyobo remembers people between conversations, such as your name and what you're learning. On the
website it recognises you through a cookie in your browser; on Telegram, through your Telegram
account. Ask Iyobo to forget you at any time and it erases what it remembers. It never saves
passwords, wallet seed phrases or payment details.

When you teach Iyobo something new, like an Edo word or a correction, it goes to the EKIOBA team for
review. It is only used, for you or anyone else, once they approve it.

## About EKIOBA

Questions this answers: what is EKIOBA, tell me about the app, about the app, about this
website, what can I do here, what do you offer, mission, platform, marketplace.

EKIOBA is a cultural e-commerce marketplace for the art, heritage and traditions of the Benin
Kingdom (Edo State, Nigeria). It connects artisans and culture-bearers with buyers worldwide, takes
payment in IDIA Coin, and offers hotels, cargo shipping and Edo language learning.

You can use EKIOBA as a website or install it on your phone as an app. Either way it offers the
same things: a store for Benin Kingdom art and craft, IDIA Coin checkout and wallet, the Edo
Language Academy, the Benin Royal Museum, hotel booking, cargo shipping, and Iyobo to guide you.

## The store

Questions this answers: products, shop, store, buy, bronze, coral, mask, plaque, beads, catalogue.

The store sells handcrafted Benin Kingdom items, including gold-plated bronze heads, Idia ivory mask
pendants, royal coral bead necklaces, vintage bronze plaques, Benin bronze castings and royal fashion
attire. Browse the Store section on the homepage and select a product to add it to your cart.

## Cart and checkout

Questions this answers: cart, basket, add to cart, order, purchase, checkout.

Add items from the Store section. The basket icon at the top right shows how many items are in your
cart. Open it to review the items, then check out with IDIA Coin. A cart checkout is a single
payment for the whole cart total, not one payment per item.

## Payments and IDIA Coin

Questions this answers: how do I pay, how to pay, pay, paying, payment, price, naira, NGN, currency,
IDIA Coin, IDIA rate, token.

IDIA Coin is the only checkout currency. Prices are shown in naira (NGN) for reference and converted
to IDIA at checkout. The payment window shows the rate used. It is labelled "Live DeDust rate" when
it comes from the market, or "Indicative rate" when it is a placeholder.

IDIA Coin is EKIOBA's cultural token, named in honour of Queen Idia, the first Queen Mother of
Benin. It is a Jetton on the TON blockchain, the only chain EKIOBA settles on. IDIA payments cannot
be reversed once they are confirmed on-chain.

IDIA Coin can also be earned at the Edo Language Academy: after passing Grades 1–4, every 100
Academy points converts to 1 IDIA, sent to the learner's wallet once the EKIOBA team has reviewed
the request.

## Wallets and TON Connect

Questions this answers: wallet, connect wallet, Tonkeeper, TON Connect, MyTonWallet, Telegram Wallet.

Select Connect Wallet at the top of the site to connect Tonkeeper, MyTonWallet, Telegram Wallet or
any other TON Connect wallet. Once connected, IDIA checkout uses that wallet automatically.

## Home dashboard and market forecast

Questions this answers: dashboard, home page, forecast, market, stocks, crypto, sentiment.

The homepage works as a dashboard: product listings, market charts (stocks, crypto and a sentiment
score), TON wallet status and your cart. Prices are live: stocks from Yahoo Finance, crypto from
whichever of Binance, Coinbase, Kraken or CoinGecko answers first, and the Crypto Fear & Greed Index
for sentiment. Every card names its source and the time the price was measured, and a card whose
provider can't be reached says so instead of showing a figure. The raw data is at
`/api/dashboard/forecast`.

The dotted line on each chart is a trend line through the closes shown, continued three steps. It is
an extrapolation of the recent slope, not a prediction of the market, and none of it is financial
advice.

## Edo Language Academy

Questions this answers: academy, learn Edo, lessons, quiz, exam, grade, pass mark, points, rewards,
convert points to IDIA, translator, vocabulary, study.

The Edo Language Academy (`/academy`) teaches the Edo (Bini) language as an institute with four
grades:

| Grade | Subject |
| ----- | ------- |
| 1 | Everyday words: nouns, family, food, nature, places and first phrases |
| 2 | Counting in Edo: numbers from one to one hundred |
| 3 | Animals and actions: animals, verbs and adverbs |
| 4 | Describing and asking: adjectival verbs, adjectives, ideophones and question particles |

- **Enrolling.** Sign in with a TON wallet. Grades, points and conversions belong to that wallet.
- **Exams.** Each grade has a 50-question exam, one question per screen. 70% passes the grade and
  unlocks the next one. Exams can be retaken, and an unfinished exam can be resumed.
- **Points.** Each correct answer is worth 10 points, but only answers beyond your best score in
  that grade earn points, so each grade is worth up to 500 points. Practice quizzes earn no points.
- **IDIA Coin.** After passing Grades 1–4, points convert at 100 points = 1 IDIA Coin. A conversion
  is a request: the EKIOBA team reviews it and sends the IDIA to your signed-in wallet. If a request
  is declined, the points are returned.

The Academy also has an English–Edo translator (EKIOBA's own recorded words first, AI-assisted for
words it doesn't yet have), a practice quiz, a vocabulary browser and daily lessons.

## Benin Royal Museum

Questions this answers: museum, Benin Royal Museum, Obas, portraits, kings of Benin.

The Benin Royal Museum (`/museum`) is a portrait gallery of 39 Obas of Benin, from Oba Eweka I to Oba
Ewuare II, in reign order and grouped by era. Each portrait's plaque gives the Oba's reign and
legacy. The portraits are contemporary artistic renderings in the Benin bronze style.

## Hotels

Questions this answers: hotel, accommodation, stay, lodging, book a hotel, Benin City, Lagos, Abuja,
Port Harcourt.

The Hotels page (`/hotels`) lists hotels in four cities. When the hotel service is offline, the site
shows these:

| City          | Hotels |
| ------------- | ------ |
| Benin City    | Protea Hotel Benin City Select Emotan; Oti Hotels Benin; Garki Hotel Benin City; Heritage Luxury Suites Benin |
| Abuja         | Transcorp Hilton Abuja; Fraser Suites Abuja |
| Lagos         | Eko Hotels & Suites; The Wheatbaker Lagos |
| Port Harcourt | Hotel Presidential Port Harcourt; Novotel Port Harcourt |

Check the Hotels page for current prices and availability.

## Cargo and shipping

Questions this answers: cargo, shipping, ship, freight, courier, logistics, send goods.

EKIOBA Cargo (`/cargo`) ships across Nigeria and internationally. Get an instant quote by entering
distance and weight, book a pickup, and track the shipment in real time. Shipments use
tamper-evident packaging, scan checkpoints, insurance for high-value cargo and set delivery windows.

## Delivery areas

Questions this answers: deliver, delivery, where do you ship, international shipping, abroad,
worldwide.

EKIOBA delivers within Nigeria (Benin City, Lagos, Abuja, Port Harcourt and all states) and
internationally. International orders use partner couriers with full customs documentation. For
high-value artworks and cultural items, contact support for a custom international quote.

## Returns and refunds

Questions this answers: return, refund, exchange, policy, dispute, cancel order.

Returns are accepted within 14 days of delivery for items in their original, undamaged condition
and packaging. IDIA Coin payments cannot be reversed once confirmed on-chain. For a dispute, contact
EKIOBA support with your order ID and photos of the item's condition.

## Contact and support

Questions this answers: contact, support, help, customer service, reach EKIOBA.

Contact EKIOBA support through the contact form on the homepage. Include your order ID, and for a
payment problem include the blockchain transaction hash. Support covers product questions, payment
issues, shipping updates and Edo cultural questions, and typically replies within 24 hours on
business days.
