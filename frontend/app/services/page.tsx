import Link from "next/link";
import PlatformMenu from "../components/PlatformMenu";
import { serviceCatalog } from "../components/serviceCatalog";

export default function ServicesPage() {
  return (
    <main className="min-h-screen px-6 py-8 md:px-10 md:py-12">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <div className="reveal">
          <PlatformMenu />
        </div>

        <section className="reveal rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-xl shadow-orange-100/60 md:p-10" style={{ animationDelay: "80ms" }}>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-orange-700">Service Directory</p>
          <h2 className="mt-3 text-3xl font-black text-slate-900 md:text-5xl">Explore all EKIOBA services</h2>
          <p className="mt-4 max-w-3xl text-base leading-relaxed text-slate-700 md:text-lg">
            Each service is built as a powerful standalone experience and engineered to work together as one
            connected platform.
          </p>
        </section>

        <section className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {serviceCatalog.map((service, index) => (
            <Link
              key={service.slug}
              href={`/services/${service.slug}`}
              className={`reveal rounded-2xl border border-slate-200 bg-gradient-to-br ${service.color} p-5 shadow-lg shadow-slate-200/50 transition hover:-translate-y-1 hover:shadow-xl`}
              style={{ animationDelay: `${140 + index * 70}ms` }}
            >
              <p className="text-xs font-bold uppercase tracking-[0.15em] text-slate-600">0{index + 1}</p>
              <h3 className="mt-2 text-xl font-extrabold text-slate-900">{service.title}</h3>
              <p className="mt-2 text-sm font-semibold text-slate-700">{service.strapline}</p>
              <p className="mt-3 text-sm leading-relaxed text-slate-700">{service.detail}</p>
            </Link>
          ))}
        </section>
      </div>
    </main>
  );
}
