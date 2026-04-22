/**
 * Tipuri pentru "Comenzi fara IND" — comenzi ADP deschise fara IND populat,
 * grupate ierarhic: agent → orders → products.
 *
 * IND e specific Adeplast; pentru SIKA endpoint-ul returneaza lista goala.
 * Sumele vin ca strings (Decimal) ca sa evitam pierderi de precizie.
 */

export type ComenziFaraIndScope = "adp" | "sika";

export interface ProductLine {
  productCode: string | null;
  productName: string | null;
  quantity: string;
  remainingQuantity: string;
  amount: string;
  remainingAmount: string;
}

export interface OrderRow {
  nrComanda: string | null;
  clientRaw: string;
  shipTo: string | null;
  storeId: string | null;
  storeName: string | null;
  status: string | null;
  dataLivrare: string | null;
  totalAmount: string;
  totalRemaining: string;
  lineItemsCount: number;
  products: ProductLine[];
}

export interface AgentGroup {
  agentId: string | null;
  agentName: string;
  ordersCount: number;
  totalAmount: string;
  totalRemaining: string;
  orders: OrderRow[];
}

export interface ComenziFaraIndResponse {
  scope: ComenziFaraIndScope;
  reportDate: string | null;
  totalOrders: number;
  totalAmount: string;
  totalRemaining: string;
  agents: AgentGroup[];
}
