# Cloud deployment

This folder is an independent deployment copy. The finished local project and
the transfer bundle are preserved. Do not upload `.private/`, `.env`, virtual
environments, database dumps or `.streamlit/secrets.toml` to GitHub.

## Hosting sequence

1. Create a GitHub repository initialized with a README, then push the curated
   contents of this folder. The root `requirements.txt` is the app runtime,
   not the original pipeline's Jupyter/Windows dependency freeze.
2. Create an Aiven **Free** MySQL service. Confirm the selected plan explicitly
   says Free; no payment method is required for this tier. Obtain its host,
   port, admin connection and CA certificate. Free services may be powered off
   after inactivity, so check availability before an interview.
3. Import the five star tables and two views into a new, empty `ecommerce_db`.
   Use the private export prepared for this deployment, rather than a laptop
   port-forward. Stop if the target already contains project tables.
4. Create a dedicated `ecommerce_reader` account and grant only SELECT on
   `ecommerce_db.*`. Check `SHOW GRANTS` and connect as the reader before using
   it in the app. Do not deploy the admin/loader account. SQL views must use a
   portable definer; use SQL SECURITY INVOKER with reader access to the tables.
5. In Streamlit Community Cloud, choose the repository, `main` branch and
   `assistant/app.py`; choose Python 3.13. Complete the example TOML and put it
   in **Advanced settings → Secrets**. `MYSQL_SSL_CA` is the provider's PEM
   certificate contents.
6. Deploy and verify the live URL. Keep the Gemini key and database password
   out of source, logs and screenshots. Only the read-only credential belongs
   in Streamlit's secrets; the admin credential stays private.

## Acceptance checks on the online URL

- Title and three KPI cards display: ₹6.97 crore shipped value, 100,227 valued
  shipped orders, and 14.21% cancelled lines for the full snapshot.
- Query Explorer works without a Gemini request.
- Gemini chat is available directly when its API key is configured and the
  session allowance remains available.
- “Show Kurta sales in Maharashtra and explain how sales are defined” produces
  SQL evidence and relevant document citations. Expected category value is
  ₹3,198,039; a top-SKU subset must not be presented as the category total.
- Cancellation/return count questions give direct line counts and explain that
  reasons are absent. Unsupported official-policy questions state that there
  are no supporting policy documents.
- A cold restart reconnects through verified TLS and reloads the existing
  17-passage index without rebuilding it or making indexing requests.
- Provider errors are sanitized; neither credentials nor raw provider details
  appear in the public interface.

The hourly shared allowance is atomic within the app process, including
concurrent visitors. Reservations include embedding requests and generation
requests; known unused capacity is returned. Unknown failures consume the
reserved capacity. A process restart resets this allowance, so it does not
replace provider quotas or billing controls.

## Official references

- [Streamlit deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Streamlit secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Aiven free MySQL](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier)
- [Aiven TLS certificates](https://aiven.io/docs/platform/concepts/tls-ssl-certificates)
- [Aiven MySQL migration](https://aiven.io/docs/products/mysql/howto/migrate-database-mysqldump)
- [Aiven service users](https://aiven.io/docs/products/mysql/howto/manage-service-users)
