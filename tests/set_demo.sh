#!/bin/bash
# Usage: set_demo.sh free 4 | starter 165 | agency 850 | reset
P=$(date -u +%Y-%m)
case "$1" in
  free) mongosh test_database --quiet --eval "db.users.updateOne({email:'demo@ledgerstream.ai'},{\$set:{plan:'free',subscription_status:'trial',pages_used:$2},\$unset:{usage_period:'',period_pages:''}})" ;;
  starter|agency) mongosh test_database --quiet --eval "db.users.updateOne({email:'demo@ledgerstream.ai'},{\$set:{plan:'$1',subscription_status:'active',usage_period:'$P',period_pages:$2}})" ;;
  reset) mongosh test_database --quiet --eval "db.users.updateOne({email:'demo@ledgerstream.ai'},{\$set:{plan:'free',subscription_status:'trial',pages_used:0},\$unset:{usage_period:'',period_pages:'',stripe_customer_id:''}})" ;;
esac
