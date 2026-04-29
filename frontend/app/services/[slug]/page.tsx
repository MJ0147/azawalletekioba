import Link from "next/link";
import { notFound } from "next/navigation";
import PlatformMenu from "../../components/PlatformMenu";
import { getServiceBySlug, serviceCatalog } from "../../components/serviceCatalog";

type ServiceRouteProps = {
  params: {
    slug: string;
  };
};

export function generateStaticParams() {
  return serviceCatalog.map((service) => ({ slug: service.slug }));
}

export default function ServiceDetailPage({ params }: ServiceRouteProps) {
  const service = getServiceBySlug(params.slug);

  if (!service) {
    notFound();
  }

  return (
    <main className="min-h-screen px-6 py-8 md:px-10 md:py-12">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-8">
        <div className="reveal">
          <PlatformMenu />
        </div>

        <section className={`reveal rounded-3xl border border-slate-200 bg-gradient-to-br ${service.color} p-7 shadow-xl shadow-slate-200/60 md:p-10`} style={{ animationDelay: "80ms" }}>
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-slate-600">Service</p>
          <h2 className="mt-2 text-4xl font-black text-slate-900 md:text-6xl">{service.title}</h2>
          <p className="mt-3 text-lg font-semibold text-slate-800">{service.strapline}</p>
          <p className="mt-5 max-w-3xl text-base leading-relaxed text-slate-700 md:text-lg">{service.detail}</p>
        </section>

        <section className="reveal rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-xl shadow-orange-100/60 md:p-8" style={{ animationDelay: "160ms" }}>
          <h3 className="text-2xl font-black text-slate-900">Core capabilities</h3>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {service.capabilities.map((capability, index) => (
              <div
                key={capability}
                className="rounded-xl border border-slate-200 bg-white p-4 text-sm font-semibold text-slate-700 shadow-sm"
              >
                <span className="mr-2 text-xs uppercase tracking-[0.14em] text-orange-600">0{index + 1}</span>
                {capability}
              </div>
            ))}
          </div>

          <div className="mt-7 flex flex-wrap gap-3">
            <Link
              href="/services"
              className="rounded-full border border-slate-900 bg-slate-900 px-5 py-2 text-sm font-semibold text-white transition hover:-translate-y-0.5 hover:bg-slate-700"
            >
              All Services
            </Link>
            <Link
              href="/about"
              className="rounded-full border border-slate-300 bg-white px-5 py-2 text-sm font-semibold text-slate-800 transition hover:-translate-y-0.5 hover:border-orange-300 hover:text-orange-700"
            >
              About Platform
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
