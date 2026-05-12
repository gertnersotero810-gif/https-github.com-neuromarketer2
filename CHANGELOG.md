# Changelog

All notable changes to the "НейроМаркетолог" v2.0 project will be documented in this file.

## [Unreleased] - 2026-05-13

### Hardened
- **Discrete Layout Synchronization**: Restricted PUT mutations strictly to `onDragStop` and `onResizeStop` event handlers, preventing coordinate saving spam during interactive dragging/resizing.
- **Native Query Cancellation**: Configured `useGetDashboard` to utilize the native React Query `signal` context inside `queryFn` for automatic HTTP cancellation, removing fake local AbortControllers.
- **True Card-Level Empty State**: Deprecated and deleted all hardcoded fallback mock metrics array on the frontend, rendering a sleek dark card-level empty state ("Нет данных для отображения") when backend returns no metrics.
- **Service-Layer Logging**: Upgraded exceptions handling in `get_widget_array` with detailed log traces (`logger.exception`), preventing silent failures when querying materialized view databases.
- **Defense-In-Depth Tenant Safety**: Added explicit validation raising a `ValueError` if a non-existent project is targeted during `save_layout` database transactions, guaranteeing layout protection.

### Added
- **Dashboard Backend API**: Created secure endpoints `/api/v1/projects/{project_id}/dashboard` (GET) and `/api/v1/projects/{project_id}/dashboard/layout` (PUT) with Row-Level Security (RLS) and FastAPI OAuth2 token validation.
- **Responsive Widget System**: Designed a flexible grid dashboard using `react-grid-layout` that supports smooth drag-and-drop, resize, and custom multi-column breakpoints.
- **Dashboard Layout Persistence**: Integrated automatic state synchronization via TanStack Query and Axios, saving user layout configurations into the PostgreSQL `dashboard_layouts` table.
- **Premium Dark Analytics UI**: Polished the dashboard with an industry-grade, highly cohesive visual layout featuring background `#0a0a0f` with radial glow, translucent cards (`#11111a`), and smooth micro-interactions.
- **KPI Number Widgets**: Built Stripe-like metric card visualization for single-number representations with upward/downward percentage trend tags.
- **Recharts Visualization Layer**: Configured dynamic rendering for `LineChart`, `BarChart`, `AreaChart`, and `PieChart` using `recharts` with customized gradients, blurred dark glassmorphism tooltips, and responsive container fitting.
- **Loading Skeletons**: Designed animated grid-aligned pulsing skeleton placeholders matching the exact card shapes to enhance visual loading transitions.

### Fixed
- **Stability and Lifecycle Fixes**: Silenced expected Axios cancellation console outputs (`Request canceled`) triggered during component unmounting inside Vitest suites and normal React lifecycles, ensuring a perfectly clean test execution.
