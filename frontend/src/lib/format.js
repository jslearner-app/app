const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export const money = (n) => (n === null || n === undefined || n === "" ? "—" : usd.format(Number(n)));

export const shortDate = (iso) =>
  iso ? new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" }) : "";

const MARKETPLACE = { defaultRate: "30", presets: ["15", "20", "25", "30"], ledger: ["Dr Bank Clearing", "Dr Commissions", "Cr Gross Sales"] };

export const PLATFORMS = [
  { id: "toast", name: "Toast", logo: "/logos/toast.svg", ...MARKETPLACE },
  { id: "doordash", name: "DoorDash", logo: "/logos/doordash.svg", ...MARKETPLACE },
  { id: "ubereats", name: "UberEats", logo: "/logos/ubereats.svg", ...MARKETPLACE },
  { id: "shopify", name: "Shopify", logo: "/logos/shopify.svg", ...MARKETPLACE },
  { id: "stripe", name: "Stripe", logo: "/logos/stripe.svg", ...MARKETPLACE },
  { id: "lawpay", name: "LawPay", logo: "/logos/lawpay.svg", fileFees: true, defaultRate: "0", presets: [], ledger: ["Dr Trust Bank", "Cr Client Trust Liability", "Dr Card Processing Fees", "Cr Operating Bank"] },
];

export const platformMeta = (id) => PLATFORMS.find((p) => p.id === id) || PLATFORMS[0];

export const platformName = (id) => PLATFORMS.find((p) => p.id === id)?.name || id;
