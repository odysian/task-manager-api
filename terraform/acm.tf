resource "aws_acm_certificate" "frontend" {
  provider = aws.us_east_1

  domain_name       = "faros.odysian.dev"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }

  tags = {
    Name = "${var.project_name}-frontend-cert"
  }
}

resource "aws_acm_certificate_validation" "frontend" {
  provider = aws.us_east_1

  certificate_arn = aws_acm_certificate.frontend.arn
}

output "certficate_validation_records" {
  description = "DNS records to add in Cloudflare for certificate validation"
  value = {
    for dvo in aws_acm_certificate.frontend.domain_validation_options : dvo.domain_name => {
      name  = dvo.resource_record_name
      type  = dvo.resource_record_type
      value = dvo.resource_record_value
    }
  }
}