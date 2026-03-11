"""Prompt template persistence and CRUD operations."""

import json
import os
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List


@dataclass
class PromptTemplate:
    """Represents a prompt template."""
    id: str
    name: str
    content: str
    description: str = ""
    built_in: bool = False
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self):
        """Convert to dictionary."""
        return asdict(self)
    
    @staticmethod
    def from_dict(data):
        """Create from dictionary."""
        return PromptTemplate(
            id=data['id'],
            name=data['name'],
            content=data['content'],
            description=data.get('description', ''),
            built_in=data.get('built_in', False),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            updated_at=data.get('updated_at', datetime.utcnow().isoformat()),
        )


class PromptStore:
    """Manages prompt template persistence."""
    
    def __init__(self, store_path: str):
        """Initialize the prompt store.
        
        Args:
            store_path: Path to JSON file for storing templates
        """
        self.store_path = store_path
        self.templates = {}
        self._load()
    
    def _load(self):
        """Load templates from JSON file."""
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        template = PromptTemplate.from_dict(item)
                        self.templates[template.id] = template
            except Exception as e:
                print(f"Warning: Failed to load prompt templates: {e}")
        
        # Ensure default template exists
        if 'default' not in self.templates:
            from templates.audit_prompt import AUDIT_GENERATION_PROMPT
            self.templates['default'] = PromptTemplate(
                id='default',
                name='Default Audit Prompt',
                content=AUDIT_GENERATION_PROMPT,
                built_in=True
            )
            self._save()
    
    def _save(self):
        """Save templates to JSON file."""
        os.makedirs(os.path.dirname(self.store_path) or '.', exist_ok=True)
        with open(self.store_path, 'w', encoding='utf-8') as f:
            data = [t.to_dict() for t in self.templates.values()]
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID."""
        return self.templates.get(template_id)
    
    def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a template by ID (alias for get)."""
        return self.get(template_id)
    
    def list(self) -> List[PromptTemplate]:
        """List all templates."""
        return list(self.templates.values())
    
    def list_templates(self) -> List[PromptTemplate]:
        """List all templates (alias for list)."""
        return self.list()
    
    def create(self, template_id: str, name: str, content: str, description: str = "") -> PromptTemplate:
        """Create a new template."""
        if template_id in self.templates:
            raise ValueError(f"Template {template_id} already exists")
        
        template = PromptTemplate(
            id=template_id,
            name=name,
            content=content,
            description=description
        )
        self.templates[template_id] = template
        self._save()
        return template
    
    def create_template(self, name: str, content: str, description: str = "") -> PromptTemplate:
        """Create a new template with auto-generated ID."""
        template_id = str(uuid.uuid4())
        return self.create(template_id, name, content, description)
    
    def update(self, template_id: str, name: str, content: str, description: str = "") -> Optional[PromptTemplate]:
        """Update an existing template."""
        if template_id == 'default':
            raise ValueError("Cannot modify the default template")
        
        if template_id not in self.templates:
            return None
        
        template = PromptTemplate(
            id=template_id,
            name=name,
            content=content,
            description=description,
            built_in=self.templates[template_id].built_in,
            created_at=self.templates[template_id].created_at,
            updated_at=datetime.utcnow().isoformat()
        )
        self.templates[template_id] = template
        self._save()
        return template
    
    def update_template(self, template_id: str, name: Optional[str] = None, content: Optional[str] = None, description: Optional[str] = None) -> Optional[PromptTemplate]:
        """Update an existing template (flexible fields)."""
        if template_id == 'default':
            raise ValueError("Cannot modify the default template")
        
        if template_id not in self.templates:
            return None
        
        template = self.templates[template_id]
        if name is not None:
            template.name = name
        if content is not None:
            template.content = content
        if description is not None:
            template.description = description
        template.updated_at = datetime.utcnow().isoformat()
        
        self._save()
        return template
    
    def delete(self, template_id: str) -> bool:
        """Delete a template. Returns True if deleted, False if not found."""
        if template_id == 'default':
            raise ValueError("Cannot delete the default template")
        
        if template_id not in self.templates:
            return False
        
        del self.templates[template_id]
        self._save()
        return True
    
    def delete_template(self, template_id: str) -> bool:
        """Delete a template (alias for delete)."""
        return self.delete(template_id)


_store_instance: Optional[PromptStore] = None


def get_store() -> PromptStore:
    """Get or create the global prompt store instance."""
    global _store_instance
    if _store_instance is None:
        store_path = os.path.join('runs', 'prompt_templates.json')
        _store_instance = PromptStore(store_path)
    return _store_instance

