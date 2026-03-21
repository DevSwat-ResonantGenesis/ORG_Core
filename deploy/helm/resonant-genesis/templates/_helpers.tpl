{{/*
Expand the name of the chart.
*/}}
{{- define "rg.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "rg.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "rg.labels" -}}
helm.sh/chart: {{ include "rg.name" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: resonant-genesis
{{- end }}

{{/*
Selector labels for a specific service
*/}}
{{- define "rg.selectorLabels" -}}
app.kubernetes.io/name: {{ .name }}
app.kubernetes.io/instance: {{ .release }}
{{- end }}

{{/*
Image reference helper
*/}}
{{- define "rg.image" -}}
{{- $registry := .global.imageRegistry -}}
{{- $tag := default .global.imageTag .svc.tag -}}
{{- printf "%s/%s:%s" $registry .svc.repository $tag -}}
{{- end }}

{{/*
Database URL helper
*/}}
{{- define "rg.databaseUrl" -}}
{{- $db := .Values.global.database -}}
{{- printf "postgresql+asyncpg://%s:$(DB_PASSWORD)@%s:%d/%s" $db.user $db.host (int $db.port) $db.name -}}
{{- end }}

{{/*
Redis URL helper
*/}}
{{- define "rg.redisUrl" -}}
{{- $r := .Values.global.redis -}}
{{- printf "redis://%s:%d/0" $r.host (int $r.port) -}}
{{- end }}
