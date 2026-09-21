# Networking module (skeleton).
#
# Responsibility: VPC across >= 2 AZs, public subnets for the ALB, private
# subnets for ECS tasks, security groups, NAT/controlled egress, and VPC
# endpoints where justified. ECS tasks must have no public IPs (security.md).
#
# Resources are added in the infrastructure task group.
