import type {
  CompanyPartner,
  CompanyRegistrationData,
  Startup
} from "@/lib/types";

export type ResolvedCompanyData = {
  cnpj?: string;
  razaoSocial?: string;
  nomeFantasia?: string;
  situacao?: string;
  abertura?: string;
  municipio?: string;
  uf?: string;
  localizacao?: string;
  cnae?: string;
  telefone?: string;
  email?: string;
  endereco?: string;
  naturezaJuridica?: string;
  porte?: string;
  capitalSocial?: string;
  socios: CompanyPartner[];
};

const INVALID_VALUES = new Set([
  "",
  "UNKNOWN",
  "NONE",
  "NOT SPECIFIED",
  "N/A",
  "NULL",
  "NÃO ENCONTRADO",
  "NAO ENCONTRADO",
  "DADOS INSUFICIENTES",
  "NÃO INFORMADO",
  "NAO INFORMADO"
]);

export function usefulText(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined;
  const text = String(value).trim();
  return INVALID_VALUES.has(text.toUpperCase()) ? undefined : text;
}

export function parseCompanyData(
  value: Startup["cnpj_data"]
): CompanyRegistrationData {
  if (!value) return {};
  if (typeof value === "object") return value;
  try {
    const parsed = JSON.parse(value) as unknown;
    return parsed && typeof parsed === "object"
      ? (parsed as CompanyRegistrationData)
      : {};
  } catch {
    return {};
  }
}

export function resolveCompanyData(startup: Startup): ResolvedCompanyData {
  const data = parseCompanyData(startup.cnpj_data);
  const raw =
    data.raw_data && typeof data.raw_data === "object" ? data.raw_data : {};
  const address = data.endereco || {};
  const contact = data.contato || {};
  const municipio =
    usefulText(data.municipio) ||
    usefulText(address.municipio) ||
    usefulText(raw.municipio);
  const uf =
    usefulText(data.uf) ||
    usefulText(address.uf) ||
    usefulText(raw.uf);
  const cnaeCode =
    usefulText(startup.cnae) ||
    usefulText(data.cnae) ||
    usefulText(raw.cnae_fiscal);
  const cnaeDescription =
    usefulText(data.cnae_descricao) ||
    usefulText(raw.cnae_fiscal_descricao);
  const socios = normalizePartners(
    startup.socios?.length ? startup.socios : data.socios
  );

  return {
    cnpj: usefulText(startup.cnpj) || usefulText(data.cnpj),
    razaoSocial:
      usefulText(data.razao_social) || usefulText(raw.razao_social),
    nomeFantasia:
      usefulText(data.nome_fantasia) || usefulText(raw.nome_fantasia),
    situacao:
      usefulText(data.situacao) ||
      usefulText(raw.descricao_situacao_cadastral),
    abertura:
      usefulText(data.data_inicio_atividade) ||
      usefulText(raw.data_inicio_atividade),
    municipio,
    uf,
    localizacao:
      [municipio, uf].filter(Boolean).join(" / ") ||
      usefulText(startup.location),
    cnae:
      [cnaeCode, cnaeDescription].filter(Boolean).join(" — ") || undefined,
    telefone:
      usefulText(contact.telefone_1) ||
      usefulText(contact.telefone) ||
      usefulText(raw.ddd_telefone_1),
    email: usefulText(contact.email) || usefulText(raw.email),
    endereco: formatAddress(address, raw),
    naturezaJuridica:
      usefulText(data.natureza_juridica) ||
      usefulText(raw.natureza_juridica),
    porte: usefulText(data.porte) || usefulText(raw.porte),
    capitalSocial: formatCapital(
      data.capital_social ?? raw.capital_social
    ),
    socios
  };
}

export function hasCompanyRegistrationData(startup: Startup) {
  const data = resolveCompanyData(startup);
  return Boolean(
    data.cnpj ||
      data.razaoSocial ||
      data.nomeFantasia ||
      data.cnae ||
      data.telefone ||
      data.email ||
      data.endereco ||
      data.municipio ||
      data.socios.length
  );
}

function normalizePartners(
  partners: CompanyPartner[] | null | undefined
): CompanyPartner[] {
  if (!Array.isArray(partners)) return [];
  return partners
    .map((partner) => ({
      ...partner,
      nome: usefulText(partner.nome) || usefulText(partner.name),
      qualificacao:
        usefulText(partner.qualificacao) || usefulText(partner.role)
    }))
    .filter((partner) => Boolean(partner.nome));
}

function formatAddress(
  address: CompanyRegistrationData["endereco"] | undefined,
  raw: Record<string, unknown>
) {
  const source = address || {};
  const street = usefulText(source.logradouro) || usefulText(raw.logradouro);
  const number = usefulText(source.numero) || usefulText(raw.numero);
  const complement =
    usefulText(source.complemento) || usefulText(raw.complemento);
  const neighborhood =
    usefulText(source.bairro) || usefulText(raw.bairro);
  const city = usefulText(source.municipio) || usefulText(raw.municipio);
  const uf = usefulText(source.uf) || usefulText(raw.uf);
  const cep = usefulText(source.cep) || usefulText(raw.cep);
  const firstLine = [street, number].filter(Boolean).join(", ");
  const cityLine = [city, uf].filter(Boolean).join(" / ");
  return [
    firstLine,
    complement,
    neighborhood,
    cityLine,
    cep ? `CEP ${cep}` : undefined
  ]
    .filter(Boolean)
    .join(" — ") || undefined;
}

function formatCapital(value: unknown) {
  if (value === null || value === undefined || value === "") return undefined;
  const numeric =
    typeof value === "number"
      ? value
      : Number(
          String(value).includes(",")
            ? String(value).replace(/\./g, "").replace(",", ".")
            : String(value)
        );
  if (!Number.isFinite(numeric)) return usefulText(value);
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL"
  }).format(numeric);
}

export function partnerName(partner: CompanyPartner) {
  return usefulText(partner.nome) || usefulText(partner.name);
}

export function partnerRole(partner: CompanyPartner) {
  return usefulText(partner.qualificacao) || usefulText(partner.role);
}
