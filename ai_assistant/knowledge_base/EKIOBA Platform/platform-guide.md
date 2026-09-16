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

Iyobo (also called Aza AI) is EKIOBA's AI cultural assistant. It runs on Grok from xAI, answers from
the EKIOBA Knowledge Base first, and uses web search to fill gaps. Anything it finds on the web is
checked against the Knowledge Base first: web information that disagrees with the Knowledge Base is
never used, and web information the Knowledge Base doesn't cover is marked as unverified. It can help you shop, check out,
learn Edo, book hotels, ship cargo and explore the heritage behind EKIOBA products. When the AI is offline,
the site chat quotes the Knowledge Base directly.

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

Questions this answers: what is EKIOBA, mission, platform, marketplace.

EKIOBA is a cultural e-commerce marketplace for the art, heritage and traditions of the Benin
Kingdom (Edo State, Nigeria). It connects artisans and culture-bearers with buyers worldwide, takes
payment in IDIA Coin, and offers hotels, cargo shipping and Edo language learning.

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

- **Academy rewards.** The earlier replies said Academy quizzes earn IDIA, but Iyobo's instructions
  say they earn Aza Points. Confirm which is correct.

## Wallets and TON Connect

Questions this answers: wallet, connect wallet, Tonkeeper, TON Connect, MyTonWallet, Telegram Wallet.

Select Connect Wallet at the top of the site to connect Tonkeeper, MyTonWallet, Telegram Wallet or
any other TON Connect wallet. Once connected, IDIA checkout uses that wallet automatically.

## Home dashboard and market forecast

Questions this answers: dashboard, home page, forecast, market, stocks, crypto, sentiment.

The homepage works as a dashboard: product listings, market forecast charts (stocks, crypto and a
sentiment score), TON wallet status and your cart. Market data comes from Yahoo Finance, Google
Finance and SoSoValue; the raw data is at `/api/dashboard/forecast`. Forecasts are not financial
advice.

## Edo Language Academy

Questions this answers: academy, learn Edo, lessons, quiz, translator, vocabulary, study.

The Edo Language Academy (`/academy`) teaches the Edo (Bini) language. It has an Edo–English
translator, a 50-question vocabulary quiz with rewards, a vocabulary browser by category, and daily
lessons. The words themselves are in the Language Academy section of this Knowledge Base.

## Benin Royal Museum

Questions this answers: museum, Benin Royal Museum, Obas, portraits, kings of Benin.

The Benin Royal Museum (`/museum`) is a portrait gallery of 38 Obas of Benin, from Oba Eweka I to Oba
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
