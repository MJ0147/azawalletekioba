import WalletView from "./components/WalletView";
import StoreProducts from "./components/StoreProducts";
import GenerativeUI from "./components/GenerativeUI";
import PlatformMenu from "./components/PlatformMenu";
import Link from "next/link";
import { serviceCatalog } from "./components/serviceCatalog";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center gap-10 px-6 py-8 md:px-10 md:py-12 text-slate-900">
      <div className="w-full reveal">
        <PlatformMenu />
      </div>

      <div className="relative flex max-w-4xl flex-col place-items-center text-center reveal" style={{ animationDelay: "80ms" }}>
        <h2 className="text-4xl font-black tracking-tight md:text-6xl">
          Welcome to Ekioba
        </h2>
        <p className="mt-4 max-w-2xl text-lg text-slate-700">
          A multi-service ecosystem where commerce, learning, travel, logistics, and market intelligence move in one rhythm.
        </p>
      </div>

      <section id="services" className="w-full max-w-6xl rounded-3xl border border-slate-200 bg-white/85 p-6 shadow-xl shadow-orange-100/50 reveal md:p-8" style={{ animationDelay: "160ms" }}>
        <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <h3 className="text-2xl font-black tracking-tight text-slate-900 md:text-3xl">Service Outline</h3>
          <p className="rounded-full bg-orange-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-orange-700">
            Store-Academy-Hotels-Tourism-Cargo-Crypto Forecasting
          </p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {serviceCatalog.map((service, index) => (
            <Link
              href={`/services/${service.slug}`}
              key={service.slug}
              className="reveal rounded-2xl border border-orange-100 bg-gradient-to-br from-white to-orange-50 p-4 shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
              style={{ animationDelay: `${220 + index * 70}ms` }}
            >
              <p className="text-xs font-bold uppercase tracking-[0.15em] text-orange-700">0{index + 1}</p>
              <h4 className="mt-2 text-lg font-extrabold text-slate-900">{service.title}</h4>
              <p className="mt-2 text-sm leading-relaxed text-slate-700">{service.detail}</p>
            </Link>
          ))}
        </div>
      </section>

      <div className="w-full max-w-4xl reveal" style={{ animationDelay: "220ms" }}>
        <GenerativeUI />
      </div>

      <section className="w-full max-w-6xl reveal" style={{ animationDelay: "280ms" }}>
        <WalletView />
      </section>

      <div className="w-full max-w-5xl reveal" style={{ animationDelay: "340ms" }}>
        <StoreProducts />
      </div>
    </main>
  );
}