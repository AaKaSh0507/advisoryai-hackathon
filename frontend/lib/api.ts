const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ApiTemplate {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface ApiJob {
  id: string;
  job_type: 'PARSE' | 'CLASSIFY' | 'GENERATE';
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  payload: Record<string, unknown>;
  result?: Record<string, unknown>;
  error?: string;
  worker_id?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ApiSection {
  id: number;
  template_version_id: string;
  section_type: 'STATIC' | 'DYNAMIC';
  structural_path: string;
  prompt_config?: Record<string, unknown>;
  created_at: string;
}

export interface ApiTemplateVersion {
  id: string;
  template_id: string;
  version_number: number;
  source_doc_path: string;
  parsed_representation_path?: string;
  parsing_status: string;
  created_at: string;
}

export interface ApiDocument {
  id: string;
  template_version_id: string;
  current_version: number;
  created_at: string;
}

export interface ApiDocumentVersion {
  id: string;
  document_id: string;
  version_number: number;
  output_doc_path: string;
  generation_metadata: Record<string, unknown>;
  created_at: string;
}

export interface ApiError {
  detail: string;
}

class ApiService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP error ${response.status}`);
    }

    return response.json();
  }

  // Templates
  async getTemplates(): Promise<ApiTemplate[]> {
    return this.request<ApiTemplate[]>('/api/v1/templates');
  }

  async getTemplate(id: string): Promise<ApiTemplate> {
    return this.request<ApiTemplate>(`/api/v1/templates/${id}`);
  }

  async createTemplate(name: string): Promise<ApiTemplate> {
    return this.request<ApiTemplate>('/api/v1/templates', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  }

  async uploadTemplateVersion(
    templateId: string,
    file: File
  ): Promise<ApiTemplateVersion> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
      `${this.baseUrl}/api/v1/templates/${templateId}/versions`,
      {
        method: 'POST',
        body: formData,
      }
    );

    if (!response.ok) {
      const error: ApiError = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || `HTTP error ${response.status}`);
    }

    return response.json();
  }

  async getTemplateVersions(templateId: string): Promise<ApiTemplateVersion[]> {
    return this.request<ApiTemplateVersion[]>(`/api/v1/templates/${templateId}/versions`);
  }

  // Jobs
  async getJobs(): Promise<ApiJob[]> {
    return this.request<ApiJob[]>('/api/v1/jobs');
  }

  async getJob(id: string): Promise<ApiJob> {
    return this.request<ApiJob>(`/api/v1/jobs/${id}`);
  }

  // Sections
  async getSectionsByTemplateVersion(templateVersionId: string): Promise<ApiSection[]> {
    return this.request<ApiSection[]>(`/api/v1/sections/template-version/${templateVersionId}`);
  }

  // Documents
  async getDocuments(): Promise<ApiDocument[]> {
    return this.request<ApiDocument[]>('/api/v1/documents/');
  }

  async getDocument(documentId: string): Promise<ApiDocument> {
    return this.request<ApiDocument>(`/api/v1/documents/${documentId}`);
  }

  async getDocumentVersions(documentId: string): Promise<ApiDocumentVersion[]> {
    return this.request<ApiDocumentVersion[]>(`/api/v1/documents/${documentId}/versions`);
  }

  async createDocument(templateVersionId: string): Promise<ApiDocument> {
    return this.request<ApiDocument>('/api/v1/documents', {
      method: 'POST',
      body: JSON.stringify({ template_version_id: templateVersionId }),
    });
  }

  // Demo
  async seedDemoData(force: boolean = false): Promise<{ success: boolean; message: string; entities: Record<string, unknown> }> {
    return this.request('/api/v1/demo/seed', {
      method: 'POST',
      body: JSON.stringify({ force }),
    });
  }

  async getDemoIds(): Promise<{ ids: Record<string, unknown> }> {
    return this.request('/api/v1/demo/ids');
  }

  // Health
  async checkHealth(): Promise<{ status: string }> {
    return this.request('/health');
  }

  async checkInfrastructure(): Promise<{ status: string; components: Record<string, boolean> }> {
    return this.request('/health/infrastructure');
  }

  // Document Download
  async downloadDocument(documentId: string, version: number): Promise<Blob> {
    const url = `${this.baseUrl}/api/v1/rendering/document/${documentId}/version/${version}/download`;
    const response = await fetch(url);

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Download failed' }));
      throw new Error(error.detail || `HTTP error ${response.status}`);
    }

    return response.blob();
  }
}

export const api = new ApiService();
