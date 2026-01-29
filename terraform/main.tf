terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

terraform {
  backend "gcs" {
    bucket = "civil-treat-482015-n6-terraform-state"
    prefix = "terraform/state"
  }
}

data "google_cloud_run_v2_service" "market_agent" {
  name     = "market-agent"
  location = "asia-southeast1"
  project  = "civil-treat-482015-n6"
}

resource "google_service_account" "scheduler" {
  project      = "civil-treat-482015-n6"
  account_id   = "market-agent-scheduler"
  display_name = "Cloud Scheduler for market-agent"
}

resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  project  = "civil-treat-482015-n6"
  location = "asia-southeast1"
  name     = "market-agent"
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

locals {
  cloud_run_uri = trimspace(data.google_cloud_run_v2_service.market_agent.uri)
  analyze_triggers = [
    { key = "eurusd", query = "Analyze EUR/USD Price today" },
    { key = "xauusd", query = "Analyze XAU/USD Price today" },
    { key = "ethusd", query = "Analyze ETH/USD Price today" },
    { key = "btcusd", query = "Analyze BTC/USD Price today" },
  ]
}

resource "google_cloud_scheduler_job" "analyze" {
  for_each         = { for t in local.analyze_triggers : t.key => t }
  name             = "market-agent-analyze-${each.value.key}"
  project          = "civil-treat-482015-n6"
  region           = "asia-southeast1"
  description      = "Trigger market_agent /analyze: ${each.value.query}"
  schedule         = "0 2 * * *"
  time_zone        = "Asia/Ho_Chi_Minh"
  attempt_deadline = "320s"

  http_target {
    uri         = "${local.cloud_run_uri}/analyze"
    http_method = "POST"
    headers = {
      "Content-Type" = "application/json"
    }
    body = base64encode(jsonencode({ query = each.value.query }))
    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = data.google_cloud_run_v2_service.market_agent.uri
    }
  }
}
