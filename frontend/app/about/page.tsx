import Link from "next/link";
import PlatformMenu from "../components/PlatformMenu";
import { serviceCatalog } from "../components/serviceCatalog";

const pillars = serviceCatalog.map((service) => ({
  title: service.title,
  slug: service.slug,
  summary: service.detail,
  energy: service.strapline,
}));

export default function AboutPage() {
  return (
    <main className="min-h-screen bg-transparent px-6 py-8 md:px-10 md:py-12">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-center gap-8">
        <div className="w-full reveal">
          <PlatformMenu />
        </div>

        <section className="w-full rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-orange-50 to-rose-100 p-7 shadow-2xl shadow-amber-200/60 reveal md:p-10" style={{ animationDelay: "80ms" }}>
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-amber-700">About EKIOBA</p>
          <h2 className="mt-3 max-w-4xl text-3xl font-black leading-tight text-slate-900 md:text-5xl">
            We build connected services that turn fragmented daily tasks into one vivid digital experience.
          </h2>
          <p className="mt-5 max-w-4xl text-base leading-relaxed text-slate-700 md:text-lg">
            EKIOBA is a multi-service platform designed to feel alive. Instead of treating commerce, education,
            travel, logistics, and market insight as separate worlds, we connect them into one ecosystem where people can
            buy, learn, stay, explore, ship, and forecast with continuity.
          </p>
          <p className="mt-4 max-w-4xl text-base leading-relaxed text-slate-700 md:text-lg">
            Every service shares a single product philosophy: reduce friction, surface useful context, and let users move
            with confidence from one life moment to the next.
          </p>
        </section>

        <section className="w-full reveal" style={{ animationDelay: "160ms" }} aria-labelledby="platform-pillars">
          <div className="mb-5 flex items-end justify-between gap-4">
            <h3 id="platform-pillars" className="text-2xl font-black text-slate-900 md:text-3xl">
              Service Pillars
            </h3>
            <span className="rounded-full bg-slate-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white">
              Six Integrated Domains
            </span>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {pillars.map((pillar, index) => (
              <Link
                href={`/services/${pillar.slug}`}
                key={pillar.slug}
                className="group reveal rounded-2xl border border-slate-200 bg-white/85 p-5 shadow-lg shadow-slate-200/50 transition hover:-translate-y-1 hover:border-orange-200"
                style={{ animationDelay: `${220 + index * 60}ms` }}
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-xl font-extrabold text-slate-900">{pillar.title}</h4>
                  <span className="rounded-full bg-orange-100 px-2.5 py-1 text-xs font-bold text-orange-700">
                    0{index + 1}
                  </span>
                </div>
                <p className="mt-3 text-sm font-semibold uppercase tracking-[0.14em] text-slate-500">{pillar.energy}</p>
                <p className="mt-3 text-sm leading-relaxed text-slate-700 md:text-base">{pillar.summary}</p>
              </Link>
            ))}
          </div>
        </section>

        <section className="w-full rounded-3xl border border-slate-200 bg-white/85 p-6 text-center shadow-xl shadow-slate-200/50 reveal md:p-10" style={{ animationDelay: "260ms" }}>
          <h3 className="text-2xl font-black text-slate-900 md:text-3xl">What this means for users</h3>
          <p className="mx-auto mt-4 max-w-3xl text-base leading-relaxed text-slate-700 md:text-lg">
            A student can become a shopper, a traveler can become a learner, and a merchant can become a logistics
            operator, all without leaving the EKIOBA environment. The platform grows with your intent, not against it.
          </p>
          <Link
            href="/"
            className="mt-6 inline-flex rounded-full border border-slate-900 bg-slate-900 px-6 py-3 text-sm font-bold uppercase tracking-[0.12em] text-white transition hover:-translate-y-0.5 hover:bg-slate-700"
          >
            Explore the Platform
          </Link>
        </section>
      </div>
    </main>
  );
}
