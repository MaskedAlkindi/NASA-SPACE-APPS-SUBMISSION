# Online demo on DigitalOcean

One script turns a fresh droplet into the public demo: the website and API, PostgreSQL, Ollama running the assistant model, the fine-tuning trainer (GPU droplets only) and HTTPS through Caddy.

## What to rent

DigitalOcean prices, checked in November 2026 on the [GPU Droplet pricing page](https://www.digitalocean.com/pricing/gpu-droplets). Check them again before you buy.

| Option | What you get | Price | Use it for |
|---|---|---|---|
| **GPU Droplet, 1× RTX 4000 Ada (recommended)** | 20 GB GPU memory, 8 vCPU, 32 GB RAM | **$0.76 per hour** (about $18 per day, about $555 per month if left on) | Demo days: Qwen2.5 7B runs fast, and QLoRA training of 7B fits in 20 GB |
| GPU Droplet, 1× L40S | 48 GB GPU memory | $1.57 per hour | Faster or larger fine-tuning runs; not needed for the demo |
| CPU Droplet (8 GB RAM or more) | No GPU | Monthly plan; see the [Droplet pricing](https://docs.digitalocean.com/products/droplets/details/pricing/) | A cheap always-on link. The assistant runs `qwen2.5:1.5b` on the CPU (slow but works); no fine-tuning |

**Cheapest plan that still impresses:**

1. Keep a small CPU droplet online for the shareable link.
2. Create the RTX 4000 Ada droplet only for the judging session and the video recording, a few hours in total.
3. Snapshot it and **destroy** it afterwards.

DigitalOcean keeps billing a powered-off droplet, so destroying it is what stops the charge.

**What to send me:** for either droplet, choose **Ubuntu 22.04 or 24.04**. On the GPU droplet the "AI/ML-ready" image has the NVIDIA drivers already. Add your SSH key, then share the droplet IP address and, optionally, a domain name pointed at it (an A record).

## Install (about 15 minutes, mostly image builds)

On the droplet:

```bash
git clone https://github.com/MaskedAlkindi/NASA-SPACE-APPS-SUBMISSION.git health01 && cd health01
```

```bash
git checkout main
```

```bash
sudo bash deploy/digitalocean/setup.sh demo.your-domain.org
```

Leave out the domain to serve plain HTTP on the IP address.

The script:

1. Installs Docker, plus the NVIDIA container toolkit when it finds a GPU.
2. Writes `.env` with random secrets and a random demo passcode (`DEMO_PASSCODE`).
3. Opens only SSH, 80 and 443 in the firewall. The API and website ports stay bound to localhost behind Caddy.
4. Starts the stack. With a GPU this is Ollama plus the trainer; without one it uses the CPU overrides.
5. Downloads the assistant model: `qwen2.5:7b` on a GPU, `qwen2.5:1.5b` on a CPU.

To update after pushing new code:

```bash
bash deploy/digitalocean/update.sh
```

## After install

| Task | How |
|---|---|
| **Fine-tuning data** | In the demo, open **AI › Fine-tuning › Sources & data**, press **Re-collect sources**, then **Rebuild dataset**. NASA's PDFs are not in the repository, so the PDF collector gathers nothing on the server until you copy `data/challenge_cache/` across (`scp`). Everything else downloads by itself. |
| **Training** | **Train** tab: choose Qwen2.5 7B and QLoRA, then **Start training**. On an RTX 4000 Ada, expect very roughly 1–2 hours for 2 epochs over 1,200 examples. That is an estimate, not a measurement; the run card records the real time. |
| **Deploying** | **Deploy to Ollama** imports the trained version, and it appears under **Models**. To make the assistant use it, set `OLLAMA_MODEL` in `.env` and run `update.sh`. |
| **Phones** | Use `https://demo.your-domain.org` as the server address in the app. |
| **Backups** | `docker compose exec db pg_dump -U hmt hmt > backup.sql`, and copy `data/llm/`. |

## Security notes for a public demo

- Change the demo passcode before sharing the link. Demo accounts can see simulated data only.
- The trainer is reachable only from inside the Docker network and checks `HMT_TRAINER_TOKEN`.
- The phone enrolment endpoint is open by design. Phones stay *pending* and cannot upload until an operator assigns them; revoke unknown devices on the Devices page.
