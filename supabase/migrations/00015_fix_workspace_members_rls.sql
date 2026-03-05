-- Fix infinite recursion in workspace_members RLS policy.
-- The members_select policy referenced workspace_members from within itself,
-- causing infinite recursion when Postgres evaluated the policy.

-- Create a SECURITY DEFINER function that bypasses RLS to get user's workspace IDs
CREATE OR REPLACE FUNCTION public.get_user_workspace_ids(uid uuid)
RETURNS SETOF uuid
LANGUAGE sql
SECURITY DEFINER
STABLE
SET search_path = public
AS $$
  SELECT workspace_id FROM public.workspace_members WHERE user_id = uid AND deleted_at IS NULL;
$$;

-- Drop and recreate the select policy using the helper function
DROP POLICY IF EXISTS "members_select" ON public.workspace_members;
CREATE POLICY "members_select" ON public.workspace_members
  FOR SELECT USING (
    workspace_id IN (SELECT public.get_user_workspace_ids(auth.uid()))
  );

-- Also fix any other policies that self-reference workspace_members
-- (workspace_data policies on other tables are fine since they reference a different table)
