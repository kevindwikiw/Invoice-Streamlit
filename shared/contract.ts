export type PackageCategory = "Utama" | "Bonus";

export interface PackageRecord {
  id: number;
  name: string;
  price: number;
  category: PackageCategory;
  description: string;
}

export interface DashboardStats {
  revenue: number;
  count: number;
  packages: number;
}

export interface InvoiceItem {
  id: string;
  description: string;
  details?: string;
  price: number;
  quantity: number;
  total: number;
  isBundle?: boolean;
}

export interface PaymentTerm {
  id: string;
  label: string;
  amount: number;
  locked?: boolean;
}

export interface InvoicePayload {
  invoiceNo: string;
  clientName: string;
  date: string;
  title: string;
  venue?: string;
  items: InvoiceItem[];
  paymentTerms: PaymentTerm[];
  cashback: number;
  totalAmount: number;
  metadata: {
    clientPhone?: string;
    clientEmail?: string;
    weddingDate?: string;
    bankName?: string;
    bankAccount?: string;
    bankAccountName?: string;
    terms?: string;
    footer?: string;
  };
}

export interface InvoiceRecord extends InvoicePayload {
  id: number;
  createdAt: string;
}

export interface ApiError {
  message: string;
}

export interface ApiResponse<T> {
  data: T;
}
