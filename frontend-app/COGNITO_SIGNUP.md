# Cognito self sign-up and email verification

The frontend uses `amazon-cognito-identity-js` directly. It calls `signUp`,
`confirmRegistration`, and `resendConfirmationCode`; it does not use an AWS
access key, client secret, or an admin-confirm API.

## AWS Console configuration

1. Open Cognito > User pools > the pool configured in `js/config.js`.
2. Under **Sign-in experience**, enable email as a sign-in option (or keep the
   existing username option if email is already the username).
3. Under **Sign-up experience**, enable self-registration.
4. Set **Cognito-assisted verification and confirmation** to send an email and
   set `email` as an auto-verified attribute.
5. Keep `email` required. Keep `name` enabled if the current sign-up form uses it.
6. Under **Message delivery**, select Cognito email for development or a verified
   SES identity for production. Check the SES sandbox and sending quota.
7. Open the app client configured in `js/config.js`. It must be a public SPA
   client **without a client secret**. Enable user-password/SRP auth and refresh
   token auth as required by the existing client.
8. Confirm that region, user-pool ID, and app-client ID match `js/config.js`.

Changing auto-verification affects new sign-ups. Existing unconfirmed users can
use the application's **Send code again** action. Admin confirmation is not part
of the normal user flow.

## Verification checklist

1. Register with an inbox you can access.
2. Confirm that Cognito creates the user as `UNCONFIRMED` and sends a six-digit code.
3. Enter the code in the confirmation form; the user must become `CONFIRMED`.
4. Register again and use **Send code again**; verify the 30-second UI cooldown.
5. Attempt login as an unconfirmed user; the app must open the confirmation form
   with the email retained.
6. Verify wrong and expired codes show distinct messages.

Never add AWS secret keys or an app-client secret to this static frontend.
