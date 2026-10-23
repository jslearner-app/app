const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const money = (n) => (n === null || n === undefined || n === "" ? "—" : usd.format(Number(n)));

export const shortDate = (iso) =>
  iso ? new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }) : "";

export const PLATFORMS = [
  { id: "toast", name: "Toast", logo: "/logos/toast.svg" },
  { id: "doordash", name: "DoorDash", logo: "/logos/doordash.svg" },
  { id: "ubereats", name: "UberEats", logo: "/logos/ubereats.svg" },
  { id: "shopify", name: "Shopify", logo: "/logos/shopify.svg" },
  { id: "stripe", name: "Stripe", logo: "/logos/stripe.svg" },
];

export const platformName = (id) => PLATFORMS.find((p) => p.id === id)?.name || id;
