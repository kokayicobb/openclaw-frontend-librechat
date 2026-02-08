import { useMemo } from 'react';
import { Blocks } from '@librechat/client';
import { Database, Bookmark, ArrowRightToLine, MessageSquareQuote, Code2, Wrench, Clock } from 'lucide-react';
import {
  Permissions,
  EModelEndpoint,
  PermissionTypes,
  isAssistantsEndpoint,
} from 'librechat-data-provider';
import type { TInterfaceConfig, TEndpointsConfig } from 'librechat-data-provider';
import type { NavLink } from '~/common';
import AgentPanelSwitch from '~/components/SidePanel/Agents/AgentPanelSwitch';
import BookmarkPanel from '~/components/SidePanel/Bookmarks/BookmarkPanel';
import PanelSwitch from '~/components/SidePanel/Builder/PanelSwitch';
import PromptsAccordion from '~/components/Prompts/PromptsAccordion';
import { MemoryPanel } from '~/components/SidePanel/Memories';
import { useHasAccess } from '~/hooks';
import SkillsAccordion from '~/components/SidePanel/Skills';
import ToolsPanel from '~/components/SidePanel/Tools';
import SueloMemoryPanel from '~/components/SidePanel/SueloMemory';
import CronJobsAccordion from '~/components/SidePanel/CronJobs';

export default function useSideNavLinks({
  hidePanel,
  keyProvided,
  endpoint,
  endpointType,
  interfaceConfig,
  endpointsConfig,
}: {
  hidePanel: () => void;
  keyProvided: boolean;
  endpoint?: EModelEndpoint | null;
  endpointType?: EModelEndpoint | null;
  interfaceConfig: Partial<TInterfaceConfig>;
  endpointsConfig: TEndpointsConfig;
}) {
  const hasAccessToPrompts = useHasAccess({
    permissionType: PermissionTypes.PROMPTS,
    permission: Permissions.USE,
  });
  const hasAccessToBookmarks = useHasAccess({
    permissionType: PermissionTypes.BOOKMARKS,
    permission: Permissions.USE,
  });
  const hasAccessToMemories = useHasAccess({
    permissionType: PermissionTypes.MEMORIES,
    permission: Permissions.USE,
  });
  const hasAccessToReadMemories = useHasAccess({
    permissionType: PermissionTypes.MEMORIES,
    permission: Permissions.READ,
  });
  const hasAccessToAgents = useHasAccess({
    permissionType: PermissionTypes.AGENTS,
    permission: Permissions.USE,
  });
  const hasAccessToCreateAgents = useHasAccess({
    permissionType: PermissionTypes.AGENTS,
    permission: Permissions.CREATE,
  });

  const Links = useMemo(() => {
    const links: NavLink[] = [];

    // Assistant Builder (only shows for assistants endpoint)
    if (
      isAssistantsEndpoint(endpoint) &&
      ((endpoint === EModelEndpoint.assistants &&
        endpointsConfig?.[EModelEndpoint.assistants] &&
        endpointsConfig[EModelEndpoint.assistants].disableBuilder !== true) ||
        (endpoint === EModelEndpoint.azureAssistants &&
          endpointsConfig?.[EModelEndpoint.azureAssistants] &&
          endpointsConfig[EModelEndpoint.azureAssistants].disableBuilder !== true)) &&
      keyProvided
    ) {
      links.push({
        title: 'com_sidepanel_assistant_builder',
        label: '',
        icon: Blocks,
        id: EModelEndpoint.assistants,
        Component: PanelSwitch,
      });
    }

    links.push({
      title: 'Skills',
      label: '',
      icon: Code2,
      id: 'skills',
      Component: SkillsAccordion,
    });

    if (hasAccessToPrompts) {
      links.push({
        title: 'com_ui_prompts',
        label: '',
        icon: MessageSquareQuote,
        id: 'prompts',
        Component: PromptsAccordion,
      });
    }

    if (hasAccessToMemories && hasAccessToReadMemories) {
      links.push({
        title: 'com_ui_memories',
        label: '',
        icon: Database,
        id: 'memories',
        Component: MemoryPanel,
      });
    }

    links.push({
      title: 'Tools',
      label: '',
      icon: Wrench,
      id: 'tools',
      Component: ToolsPanel,
    });

    links.push({
      title: 'Suelo Memory',
      label: '',
      icon: Database,
      id: 'suelo-memory',
      Component: SueloMemoryPanel,
    });

    if (hasAccessToBookmarks) {
      links.push({
        title: 'com_sidepanel_conversation_tags',
        label: '',
        icon: Bookmark,
        id: 'bookmarks',
        Component: BookmarkPanel,
      });
    }

    // Agent Builder — moved down, above Cron Jobs
    if (
      endpointsConfig?.[EModelEndpoint.agents] &&
      hasAccessToAgents &&
      hasAccessToCreateAgents &&
      endpointsConfig[EModelEndpoint.agents].disableBuilder !== true
    ) {
      links.push({
        title: 'com_sidepanel_agent_builder',
        label: '',
        icon: Blocks,
        id: EModelEndpoint.agents,
        Component: AgentPanelSwitch,
      });
    }

    links.push({
      title: 'Cron Jobs',
      label: '',
      icon: Clock,
      id: 'cron-jobs',
      Component: CronJobsAccordion,
    });

    links.push({
      title: 'com_sidepanel_hide_panel',
      label: '',
      icon: ArrowRightToLine,
      onClick: hidePanel,
      id: 'hide-panel',
    });

    return links;
  }, [
    endpoint,
    endpointsConfig,
    keyProvided,
    hasAccessToAgents,
    hasAccessToCreateAgents,
    hasAccessToPrompts,
    hasAccessToMemories,
    hasAccessToReadMemories,
    hasAccessToBookmarks,
    hidePanel,
  ]);

  return Links;
}
