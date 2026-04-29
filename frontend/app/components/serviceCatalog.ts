export type ServiceItem = {
  title: string;
  slug: string;
  strapline: string;
  detail: string;
  capabilities: string[];
  color: string;
};

export const serviceCatalog: ServiceItem[] = [
  {
    title: "Store",
    slug: "store",
    strapline: "Commerce made frictionless",
    detail:
      "Digital and physical product marketplace with seamless discovery, checkout, and order confidence.",
    capabilities: ["Product discovery", "Secure checkout", "Merchant operations"],
    color: "from-orange-50 to-amber-100",
  },
  {
    title: "Academy",
    slug: "academy",
    strapline: "Learning with momentum",
    detail:
      "Skill and language learning powered by guided lessons, quizzes, and personalized progression paths.",
    capabilities: ["Daily lessons", "Adaptive quizzes", "Progress insights"],
    color: "from-emerald-50 to-lime-100",
  },
  {
    title: "Hotels",
    slug: "hotels",
    strapline: "Hospitality with precision",
    detail:
      "Reservation and guest-flow tools for hospitality operators who need better occupancy visibility.",
    capabilities: ["Reservation tools", "Rate visibility", "Guest lifecycle"],
    color: "from-sky-50 to-cyan-100",
  },
  {
    title: "Tourism",
    slug: "tourism",
    strapline: "Trips that feel curated",
    detail:
      "Destination planning and local experience curation that help travelers discover authentic moments.",
    capabilities: ["Route planning", "Local experiences", "Guide connections"],
    color: "from-fuchsia-50 to-rose-100",
  },
  {
    title: "Cargo",
    slug: "cargo",
    strapline: "Logistics with visibility",
    detail:
      "Shipment coordination and status tracking for reliable movement across routes and regions.",
    capabilities: ["Shipment tracking", "Route orchestration", "Delivery accountability"],
    color: "from-slate-100 to-stone-200",
  },
  {
    title: "Crypto Forecasting",
    slug: "crypto-forecasting",
    strapline: "Signals over noise",
    detail:
      "Market trend monitoring and forecasting context to support sharper digital asset decision-making.",
    capabilities: ["Trend signals", "Scenario views", "Market awareness"],
    color: "from-indigo-50 to-violet-100",
  },
];

export function getServiceBySlug(slug: string) {
  return serviceCatalog.find((service) => service.slug === slug);
}
