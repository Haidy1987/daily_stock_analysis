# -*- coding: utf-8 -*-
"""Admin user management schemas."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class AdminUserSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: int
    username: str
    email: Optional[str] = None
    role: str
    status: str
    created_at: Optional[str] = Field(default=None, alias="createdAt")
    updated_at: Optional[str] = Field(default=None, alias="updatedAt")
    last_login_at: Optional[str] = Field(default=None, alias="lastLoginAt")


class AdminUserListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    items: List[AdminUserSummary]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")


class CreateAdminUserRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    role: Literal["admin", "user"] = "user"
    email: Optional[str] = None


class UpdateAdminUserRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: Optional[Literal["admin", "user"]] = None
    status: Optional[Literal["active", "disabled"]] = None
    email: Optional[str] = None


class ResetAdminUserPasswordRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    new_password: str = Field(alias="newPassword", min_length=6, max_length=128)
