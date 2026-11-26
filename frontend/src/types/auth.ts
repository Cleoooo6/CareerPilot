export interface AuthUserDto {
  id: string
  email: string | null
  display_name: string
  status: string
  email_verified: boolean
  is_demo: boolean
}

export interface AuthSessionDto {
  user: AuthUserDto
  csrf_token: string
  email_verification: string
  session_expires_at: string
}

export interface AuthMessageDto {
  message: string
  delivery?: string | null
}