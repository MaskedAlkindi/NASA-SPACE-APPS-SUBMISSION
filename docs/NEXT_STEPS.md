# Next steps: GPU server, iPhone, Apple Watch, iPad

## 1. Push

```bash
git push origin main
```

## 2. GPU droplet (serious edition, private)

1. Create the droplet:
   - DigitalOcean › GPU Droplets › **RTX 4000 Ada** (or larger)
   - image **AI/ML Ready (Ubuntu)**
   - add your SSH key
2. Optional: point a domain (A record) at the droplet IP.
3. Connect:

   ```bash
   ssh root@<DROPLET_IP>
   ```

4. Get the code:

   ```bash
   git clone https://github.com/MaskedAlkindi/NASA-SPACE-APPS-SUBMISSION.git health01 && cd health01
   ```

5. Run the setup. Leave out the domain to use the IP.

   ```bash
   bash deploy/digitalocean/setup.sh your-domain.org
   ```

6. Open `https://your-domain.org` (or `http://<DROPLET_IP>`) and enter the password **staydetermined**.
7. Read your login passcode from the server:

   ```bash
   grep DEMO_PASSCODE .env
   ```

Users: `mission-control`, `flight-surgeon`, `pilot` (your real data).

- Change the password: set `SITE_PASSWORD=` in `.env`, then run `bash deploy/digitalocean/update.sh`.
- Stop paying: snapshot the droplet, then destroy it. A powered-off droplet is still billed.

## 3. iPhone + Apple Watch

1. On the Mac, open `ios/HealthMonitor/HealthMonitor.xcodeproj` in Xcode.
2. Under **Signing & Capabilities**, pick your team and keep **HealthKit** on.
3. Plug in the iPhone and press **Run**.
4. In the app, open **Connect** and enter the server address (`https://your-domain.org`). Tap **Connect**; the app shows its device ID.
5. On the website, open **Devices**. Find the phone (first characters of the ID) and assign it to **PILOT**.
6. On the phone, open **Health**. Allow each data type, then tap **Sync last 14 days**.

Watch data reaches the server through Apple Health on the iPhone (heart rate, resting HR, HRV, sleep, exercise). Sync again any time.

**Exercise:** pick a movement, then **Start**. Counts are saved to PILOT's history.

## 4. iPad

1. Open the same address in Safari.
2. Choose Share › **Add to Home Screen**.

The layout switches to an icon sidebar on tablets. All computation runs on the server; the iPad only displays.

## 5. Optional: fine-tune Qwen2.5 7B on the droplet

1. Go to **AI › Fine-tuning**.
2. Press **Re-collect sources**, then **Rebuild dataset**.
3. On **Train**, choose Qwen2.5 7B and start it.
4. **Evaluate**, then **Deploy to Ollama**.

NASA's PDFs aren't in git. To include them, copy `data/challenge_cache/` to the server first:

```bash
scp -r data/challenge_cache root@<DROPLET_IP>:health01/data/
```
