# Pagos reales en modo prueba con Stripe

Para mostrar que Grifter no es solo una simulación: el agente de `examples/stripe_test_mode.py` cobra de verdad en la **API de Stripe en modo prueba** (sin dinero real). El pago legítimo queda cobrado; el de la estafa queda retenido, y se ve en el panel de Stripe.

Cómo funciona, sin el paquete `stripe` (solo `urllib`):

| Caso | Qué hace el ejemplo en Stripe |
|---|---|
| Pago a la cuenta inscrita | Crea un PaymentIntent con `confirm=true` y la tarjeta de prueba `pm_card_visa`: estado `succeeded`. |
| Pago que Grifter retiene (la cuenta salió de un correo) | Crea el PaymentIntent **sin confirmar**: queda en `requires_confirmation`, con `metadata[grifter]=retenido` y `metadata[motivo]`. |
| El dueño aprueba (`avisar` devuelve `True`) | Confirma ese mismo PaymentIntent y le pone `metadata[grifter]=aprobado_por_dueno`. |

Todos llevan `metadata[cuenta_destino]` y `metadata[beneficiario]`.

## Paso a paso

1. **Crea una cuenta de Stripe** en <https://dashboard.stripe.com/register>. No necesitas activar pagos reales ni dar datos del negocio.
2. En el panel, activa el **modo prueba** (el interruptor «Test mode» / «Entorno de prueba»).
3. Ve a **Developers → API keys** y copia la **llave secreta de modo prueba** (`sk_test_...`; hay que revelarla).
4. Pégala en tu `.env`, que nunca entra al repo:
   ```
   STRIPE_TEST_KEY=sk_test_...
   ```
   Con `python-dotenv` instalado, el ejemplo lee el `.env`; si no, exporta la variable en tu terminal.
5. Corre el ejemplo:
   ```bash
   python examples/stripe_test_mode.py
   ```
   Usa `claude-haiku-4-5` y necesita `ANTHROPIC_API_KEY`. Si no quieres usar Anthropic, `--modelo-falso` usa un modelo de mentira con el Stripe de prueba de verdad. Con `--aprobar` simula que el dueño aprueba lo retenido.

Sin llaves ni red, `python examples/stripe_test_mode.py --mock` corre todo con un Stripe falso.

## Qué buscar en el panel

Abre **Payments** con el modo prueba activo (<https://dashboard.stripe.com/test/payments>):

- Un pago de **CLP 412.000** en estado **Succeeded**, con `cuenta_destino = 33-7741-0092`: el pago legítimo.
- Otro de **CLP 412.000** en estado **Incomplete** (`requires_confirmation`), con `cuenta_destino = 90-1188-4417`, `grifter = retenido` y el motivo en la metadata: la estafa que Grifter retuvo. No se cobró.
- Con `--aprobar`, el segundo también pasa a **Succeeded** y su metadata dice `aprobado_por_dueno`.

## Seguridad

- **Solo llaves de prueba.** El ejemplo rechaza cualquier llave que no empiece con `sk_test_` antes de hacer una sola llamada, y nunca imprime la llave.
- Las pruebas (`tests/test_stripe_test_mode.py`) usan un cliente HTTP falso: no tocan la red ni Stripe.
- El monto va en pesos chilenos (`clp`), que Stripe trata sin decimales.
