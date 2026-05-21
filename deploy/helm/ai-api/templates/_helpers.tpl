{{- define "ai-api.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ai-api.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "ai-api.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ai-api.labels" -}}
app.kubernetes.io/name: {{ include "ai-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "ai-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
