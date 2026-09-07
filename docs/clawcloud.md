# Deploy Story Weaver on ClawCloud Run

The GitHub workflow **Build Story Weaver image** builds the committed application,
checks that it starts and rejects guest writes, and publishes it to GitHub Container
Registry. Application changes pushed to `main` trigger the workflow. It can also be
started manually from GitHub Actions on `main`. Builds use GitHub's runner.

The image contains only the Python application, dependencies, and frontend. Local
`.env` files, Firebase credentials, stories, Git history, and debug files are excluded.
Runtime secrets belong in ClawCloud's environment settings, never in the image.

## Account and image access

Sign in at [ClawCloud Run](https://run.claw.cloud/) and link the intended GitHub
account. Account linking for credits and deploying code are separate steps.
The documented [App Launchpad](https://docs.run.claw.cloud/clawcloud-run/guide/app-launchpad)
accepts container images, including private images with registry credentials.

Open the repository's **Actions** page and wait for **Build Story Weaver image**
to succeed. Its summary provides an image tag tied to the exact Git commit:

```text
ghcr.io/surajpaswan123/story-weaver:<full-commit-sha>
```

The tag `ghcr.io/surajpaswan123/story-weaver:main` also points to the last
successfully published build. Prefer the commit tag when deploying or rolling back.
Publishing a new `main` image does not automatically restart a ClawCloud application;
update the selected commit tag and deploy it in App Launchpad.

New GitHub container packages are private by default, even for public repositories.
Either make this source-only package public in GitHub's package settings, or use
ClawCloud's private-image option with a GitHub username and a classic access token
that has `read:packages`. Do not reuse an AI-provider key as a registry password.
See [GitHub's Container registry documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

## App Launchpad configuration

Create one application for Story Weaver with these settings:

| Setting | Value |
| --- | --- |
| Image | The successfully built commit tag above |
| Instances | Fixed, 1 |
| CPU | 0.5 vCPU |
| Memory | 1 GB |
| Container port | 8000, HTTP |
| Public network | Enabled, with the generated HTTPS address |
| Command / arguments | Leave unset to use the image's startup command |
| HTTP health probe, if available | GET `/ping` on port 8000 |

Use one process and one instance because active turns and story locks live in
memory. The image already sets `HOST=0.0.0.0`, `PORT=8000`, `RELOAD=false`,
`ALLOW_UNVERIFIED_JWT=false`, and `ALLOW_LOCAL_SUPER_ADMIN=false`.

Configure these runtime environment variables using the existing deployment's
values so the same accounts and saved stories remain available:

| Variable | Value to supply |
| --- | --- |
| `DATABASE_URL` | The existing Neon/Postgres connection URL, retaining its SSL parameters |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | The complete JSON for the existing Firebase Admin service account |
| `TRUST_PROXY_HEADERS` | `false`, unless the proxy has been verified to overwrite client headers |

Provider keys normally remain in each signed-in user's Settings. A new AI key is
not needed for this deployment. Firebase and Postgres are existing external
services; this configuration does not create another database.

Successful story saves persist in Postgres. The container's `/app/stories` directory
is a local cache, and changes that fail to sync can be lost on restart. If adding a
persistent volume later, ensure the mount is writable by the container's UID/GID
`10001:10001`; mounting a root-owned directory without matching permissions prevents
startup. Do not mount over `/app`, which contains the application.

ClawCloud's [published pricing](https://run.claw.cloud/pricing) lists $4 per
vCPU-month and $2 per GB-month: 0.5 CPU plus 1 GB is approximately $4/month in
compute, before storage and traffic. The advertised $5 monthly credit requires an
eligible linked GitHub account older than 180 days. Verify current eligibility,
balance, and the console's price estimate before launching; resources are not an
unlimited free allocation.

## Finish the deployment

1. Add the generated hostname (without `https://` or a path) under the existing
   Firebase project's **Authentication > Settings > Authorized domains**.
2. Deploy and check that the new HTTPS URL's `/ping` returns HTTP 200 and `OK`.
3. Sign in and open an existing story to verify both Firebase and Postgres access.
   `/ping` checks liveness only; it does not validate credentials or saved data.
4. Use the new site for subsequent edits. Avoid editing the same story through
   Render and ClawCloud at the same time because locks are local to each instance.
5. Once the new deployment is confirmed, decide whether to retire the old Render
   service and its scheduled warm-up job. Creating or updating this image does not
   remove the existing Render service.

Cron-job.org can use the new HTTPS URL followed by `/ping`, with a GET request
and no credentials. This returns a two-byte response rather than the full page.
