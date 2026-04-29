import Link from "next/link";
import { serviceCatalog } from "./serviceCatalog";

export default function PlatformMenu() {
  return (
    <header className="w-full max-w-6xl rounded-3xl border border-slate-200/80 bg-white/80 px-5 py-4 shadow-xl shadow-orange-100 backdrop-blur-sm md:px-8 md:py-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.26em] text-slate-500">
            EKIOBA Multi-Service Platform
          </p>
          <h1 className="text-2xl font-black tracking-tight text-slate-900 md:text-3xl">
            One Platform, Six Living Economies
          </h1>
        </div>

        <nav className="flex flex-wrap gap-2 md:justify-end" aria-label="Primary">
          <Link
            href="/"
            className="rounded-full border border-slate-900 bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-700"
          >
            Home
          </Link>
          <Link
            href="/about"
            className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-orange-300 hover:text-orange-700"
          >
            About
          </Link>
          <Link
            href="/services"
            className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-orange-300 hover:text-orange-700"
          >
            Services
          </Link>
        </nav>
      </div>

      <div className="mt-4 flex flex-wrap gap-2 md:mt-5">
        {serviceCatalog.map((service, index) => (
          <Link
            key={service.slug}
            href={`/services/${service.slug}`}
            className="rounded-xl border border-orange-100 bg-gradient-to-br from-white to-orange-50 px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:-translate-y-1 hover:border-orange-300 hover:shadow-md"
            style={{ transform: `rotate(${index % 2 === 0 ? "-0.7deg" : "0.7deg"})` }}
          >
            {service.title}
          </Link>
        ))}
      </div>
    </header>
  );
}
