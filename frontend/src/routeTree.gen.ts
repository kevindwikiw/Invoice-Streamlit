import { Route as RootRoute } from "./routes/__root";
import { Route as IndexRoute } from "./routes/index";
import { Route as InvoicesRoute } from "./routes/invoices";

export const routeTree = RootRoute.addChildren([IndexRoute, InvoicesRoute]);
