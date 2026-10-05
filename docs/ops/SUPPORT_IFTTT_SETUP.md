# Support filing email through IFTTT

Authority: DOM-SUP-001 §XI and FEAT-SUP-001 v1.1.

1. Create an IFTTT applet with Webhooks **Receive a web request** (the trigger
   with three values). Set the event name to `cth_support_issue`.
2. Choose your email action and configure its recipient in IFTTT.
3. Suggested subject: `CTH support: {{Value1}}`.
4. Suggested body:

   ```text
   {{Value1}}
   UTC time: {{Value3}}
   Ticket reference: {{Value2}}
   Open: https://YOUR_APP_ORIGIN/sysadmin/issues/{{Value2}}
   ```

   Replace `YOUR_APP_ORIGIN` with the application hostname. The link still
   requires Cloudflare Access and normal operator authentication/visibility.
5. Obtain the Webhooks key from IFTTT's Webhooks documentation page. Configure
   `SUPPORT_IFTTT_EVENT=cth_support_issue` and `SUPPORT_IFTTT_KEY` in the app server's
   secret environment, then restart through the approved deployment process.
   Keep the key out of source control and command/log output.

Both variables unset disables notifications. Partial configuration records a
configuration failure when a ticket action commits. The destination is fixed
to `https://maker.ifttt.com/trigger/{event}/with/key/{key}`; the implementation
does not accept an arbitrary destination URL.

Teacher filing sends **New teacher support ticket**. Teacher escalation of an
existing student issue sends **Student support ticket escalated by teacher**.
Student filing alone sends nothing. No report title or other free text is sent.

The app makes one post-commit HTTPS attempt with a three-second socket timeout.
It logs `support_notification_delivered` for IFTTT acceptance, or
`support_notification_delivery_failed` with a fixed reason and optional HTTP
status. Acceptance is not proof of email delivery. There is no retry or durable
queue; the committed ticket remains available in the support dashboard.

Validate in an authorized environment by filing a synthetic teacher ticket,
then filing a synthetic student ticket and escalating it as its owning teacher.
Confirm no email for student filing, one email for each qualifying action, and
that links open the corresponding tickets after authentication. Local tests mock
IFTTT; they do not send email or verify production configuration.

Protocol reference: [IFTTT Webhooks service FAQ](https://help.ifttt.com/hc/en-us/articles/115010230347-Webhooks-service-FAQ).
