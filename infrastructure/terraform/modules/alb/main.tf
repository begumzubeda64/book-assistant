# ALB module (skeleton).
#
# Responsibility: internet-facing Application Load Balancer (the only public
# entry point), HTTPS listener + ACM certificate, target group, and the /health
# health check. HTTP redirects to HTTPS.
#
# Resources are added in the infrastructure task group.
